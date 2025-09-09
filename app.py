from flask import Flask, jsonify, render_template, redirect, url_for, request, session
from werkzeug.utils import secure_filename
from datetime import datetime
import os, qrcode
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for session management

# Supabase setup
SUPABASE_URL = "https://hdzblqzidgwaqbaqyyaz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhkemJscXppZGd3YXFiYXF5eWF6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc0MjIxNTYsImV4cCI6MjA3Mjk5ODE1Nn0.G2cXOescsoOej5eNzrJzTkVCyjpbVPNhx8UeXM_HPrA"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Notification helpers ---
def get_notifications():
    return session.get('notifications', [])
def add_notification(msg):
    notes = session.get('notifications', [])
    notes.append(msg)
    session['notifications'] = notes
def clear_notifications():
    session['notifications'] = []

# --- Routes ---

@app.route("/")
def root():
    return redirect(url_for('welcome'))

@app.route("/welcome")
def welcome():
    return render_template("welcome.html")

@app.route("/choose")
def choose_role():
    role = request.args.get('role')
    if role == 'buyer':
        return redirect(url_for('shop_index'))
    elif role == 'seller':
        return redirect(url_for('seller_login'))
    return redirect(url_for('welcome'))

# ---------- Seller Registration/Login ----------

@app.route("/seller_register", methods=["GET", "POST"])
def seller_register():
    error = None
    if request.method == "POST":
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')

        if not (name and email and phone and password):
            error = "All fields are required."
        else:
            existing = supabase.table("sellers").select("*").eq("email", email).execute()
            if existing.data:
                error = "Email already registered. Please login."
            else:
                supabase.table("sellers").insert({
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "password": password,
                    "role": "Seller"
                }).execute()
                session['seller_logged_in'] = True
                session['seller_email'] = email
                return redirect(url_for('dashboard'))

    return render_template("seller_register.html", error=error)

@app.route("/seller_login", methods=["GET", "POST"])
def seller_login():
    error = None
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')

        seller = supabase.table("sellers").select("*").eq("email", email).eq("password", password).execute()
        if seller.data:
            session['seller_logged_in'] = True
            session['seller_email'] = email
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid email or password."

    return render_template("seller_login.html", error=error)

# ---------- Shop ----------

@app.route("/shop")
def shop_index():
    products = supabase.table("products").select("*").execute().data
    return render_template("index.html", data=products)

@app.route("/add")
def add_page():
    if not session.get('seller_logged_in'):
        return redirect(url_for('seller_login'))
    email = session.get('seller_email')
    products = supabase.table("products").select("*").eq("seller_email", email).execute().data
    return render_template("add.html", data=products)

@app.route("/add_product", methods=['POST'])
def add_product():
    if not session.get('seller_logged_in'):
        return redirect(url_for('seller_login'))
    email = session.get('seller_email')

    product_name = request.form.get('product_name')
    product_price = request.form.get('product_price')
    stock = request.form.get('stock')
    image_file = request.files.get('product_image')

    images_dir = os.path.join('static', 'images')
    os.makedirs(images_dir, exist_ok=True)
    image_name = secure_filename(image_file.filename)
    image_file.save(os.path.join(images_dir, image_name))

    supabase.table("products").insert({
        "product_name": product_name,
        "product_price": product_price,
        "stock": stock,
        "image_path": image_name,
        "seller_email": email
    }).execute()

    products = supabase.table("products").select("*").eq("seller_email", email).execute().data
    return render_template("add.html", data=products)

# ---------- Orders ----------

@app.route("/buy_product", methods=["POST"])
def buy_product():
    product_name = request.form.get('product_name')
    product_price = request.form.get('product_price')
    image_path = request.form.get('image_path')
    buyer_name = request.form.get('buyer_name')
    buyer_phone = request.form.get('buyer_phone')
    buyer_email = request.form.get('buyer_email')
    buyer_address = request.form.get('buyer_address')
    quantity = int(request.form.get('quantity'))

    product = supabase.table("products").select("*").eq("product_name", product_name).eq("image_path", image_path).execute().data
    if not product:
        return jsonify({"status": "error", "message": "Product not found"}), 404
    product = product[0]

    # Create order
    supabase.table("orders").insert({
        "product_name": product_name,
        "product_price": product_price,
        "image_path": image_path,
        "buyer_name": buyer_name,
        "buyer_phone": buyer_phone,
        "buyer_email": buyer_email,
        "buyer_address": buyer_address,
        "quantity": quantity,
        "seller_email": product['seller_email'],
        "delivered": False,
        "timestamp": datetime.now().isoformat()
    }).execute()

    # Update stock
    new_stock = int(product['stock']) - quantity
    supabase.table("products").update({"stock": new_stock}).eq("product_name", product_name).eq("image_path", image_path).execute()

    add_notification(f"New order from {buyer_name} for {product_name} (Qty: {quantity})")
    return jsonify({"status": "success"})

# ---------- Dashboard ----------

@app.route("/dashboard")
def dashboard():
    if not session.get('seller_logged_in'):
        return redirect(url_for('seller_login'))
    email = session.get('seller_email')

    profile_data = supabase.table("sellers").select("*").eq("email", email).execute().data
    profile_data = profile_data[0] if profile_data else {}

    orders = supabase.table("orders").select("*").eq("seller_email", email).execute().data

    notifications = get_notifications()
    clear_notifications()

    total_sales = sum(int(o.get('quantity', 0)) for o in orders)
    delivered_orders = sum(1 for o in orders if o.get('delivered'))
    pending_orders = sum(1 for o in orders if not o.get('delivered'))

    best_selling = {}
    for o in orders:
        pname = o.get('product_name')
        qty = int(o.get('quantity', 1))
        best_selling[pname] = best_selling.get(pname, 0) + qty
    best_selling_products = sorted(best_selling.items(), key=lambda x: x[1], reverse=True)[:3]

    return render_template("dashboard.html", profile=profile_data, notifications=notifications,
        total_sales=total_sales, delivered_orders=delivered_orders,
        pending_orders=pending_orders, best_selling_products=best_selling_products)

# ---------- Profile ----------

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if not session.get('seller_logged_in'):
        return redirect(url_for('seller_login'))
    email = session.get('seller_email')
    profile_data = supabase.table("sellers").select("*").eq("email", email).execute().data
    profile_data = profile_data[0] if profile_data else {}
    message = None

    if request.method == "POST":
        update_data = {
            "name": request.form.get('name', profile_data.get('name')),
            "phone": request.form.get('phone', profile_data.get('phone'))
        }
        if 'profile_pic' in request.files and request.files['profile_pic'].filename:
            pic = request.files['profile_pic']
            filename = secure_filename(pic.filename)
            img_path = os.path.join('static', 'images', filename)
            pic.save(img_path)
            update_data['image_path'] = filename
        supabase.table("sellers").update(update_data).eq("email", email).execute()
        message = "Profile updated successfully!"
        profile_data.update(update_data)

    return render_template("profile.html", profile=profile_data, message=message)

# ---------- Run app ----------

if __name__ == "__main__":
    app.run(debug=True, port=2008)
