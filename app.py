from flask import Flask, jsonify, render_template, redirect, url_for, request, send_from_directory, flash, session, send_file
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import qrcode
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Supabase config
SUPABASE_URL = "https://hdzblqzidgwaqbaqyyaz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhkemJscXppZGd3YXFiYXF5eWF6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc0MjIxNTYsImV4cCI6MjA3Mjk5ODE1Nn0.G2cXOescsoOej5eNzrJzTkVCyjpbVPNhx8UeXM_HPrA"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------
# Helpers
# ---------------------
def get_notifications():
    return session.get('notifications', [])

def add_notification(msg):
    notes = session.get('notifications', [])
    notes.append(msg)
    session['notifications'] = notes

def clear_notifications():
    session['notifications'] = []

# ---------------------
# Routes
# ---------------------

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
        return redirect(url_for('index'))
    elif role == 'seller':
        return redirect(url_for('seller_login'))
    return redirect(url_for('welcome'))

# ---------------------
# Shop / Products
# ---------------------
@app.route("/shop")
def index():
    try:
        products_resp = supabase.table("products").select("*").execute()
        data = products_resp.data
    except:
        data = []
    return render_template("index.html", data=data)

@app.route("/add")
def get():
    if not session.get('seller_logged_in'):
        return redirect(url_for('seller_login'))
    email = session.get('seller_email')
    try:
        products_resp = supabase.table("products").select("*").eq("seller_email", email).execute()
        products = products_resp.data
    except:
        products = []
    return render_template("add.html", data=products)

@app.route("/add_product", methods=['POST'])
def product_info():
    if not session.get('seller_logged_in'):
        return redirect(url_for('seller_login'))

    email = session.get('seller_email')
    image_file = request.files['product_image']
    product_name = request.form['product_name']
    product_price = request.form['product_price']
    stock = request.form['stock']

    images_dir = os.path.join('static', 'images')
    os.makedirs(images_dir, exist_ok=True)
    image_name = secure_filename(image_file.filename)
    image_path = os.path.join(images_dir, image_name)
    image_file.save(image_path)

    supabase.table("products").insert({
        "product_name": product_name,
        "product_price": product_price,
        "stock": stock,
        "seller_email": email,
        "image_path": image_name
    }).execute()

    return redirect(url_for('get'))

# ---------------------
# Buy Product / Orders
# ---------------------
@app.route("/buy_product", methods=['POST'])
def buy_product():
    product_name = request.form['product_name']
    product_price = request.form['product_price']
    image_path = request.form['image_path']
    buyer_name = request.form['buyer_name']
    buyer_phone = request.form['buyer_phone']
    buyer_email = request.form['buyer_email']
    buyer_address = request.form['buyer_address']
    quantity = int(request.form['quantity'])

    # Get seller_email for the product
    product_resp = supabase.table("products").select("*").eq("product_name", product_name).eq("image_path", image_path).execute()
    product = product_resp.data[0] if product_resp.data else None
    if not product:
        return jsonify({"status": "error", "message": "Product not found"}), 404

    seller_email = product['seller_email']

    # Insert order
    supabase.table("orders").insert({
        "product_name": product_name,
        "product_price": product_price,
        "image_path": image_path,
        "buyer_name": buyer_name,
        "buyer_phone": buyer_phone,
        "buyer_email": buyer_email,
        "buyer_address": buyer_address,
        "quantity": quantity,
        "seller_email": seller_email,
        "delivered": False,
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }).execute()

    # Update stock
    new_stock = max(int(product['stock']) - quantity, 0)
    supabase.table("products").update({"stock": new_stock}).eq("product_name", product_name).eq("image_path", image_path).execute()

    add_notification(f"New order from {buyer_name} for {product_name} (Qty: {quantity})")
    return jsonify({'status': 'success'})

# ---------------------
# Seller Register / Login
# ---------------------
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
            # Check if email exists
            existing = supabase.table("sellers").select("*").eq("email", email).execute()
            if existing.data:
                error = "Email already registered. Please login."
            else:
                supabase.table("sellers").insert({
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "password": password,
                    "image_url": "default-profile.png"
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
        seller_resp = supabase.table("sellers").select("*").eq("email", email).eq("password", password).execute()
        if seller_resp.data:
            session['seller_logged_in'] = True
            session['seller_email'] = email
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid email or password."
    return render_template("seller_login.html", error=error)

# ---------------------
# Dashboard
# ---------------------
@app.route("/dashboard")
def dashboard():
    if not session.get('seller_logged_in'):
        return redirect(url_for('seller_login'))
    email = session.get('seller_email')
    seller_resp = supabase.table("sellers").select("*").eq("email", email).execute()
    profile_data = seller_resp.data[0] if seller_resp.data else {}
    notifications = get_notifications()
    clear_notifications()

    orders_resp = supabase.table("orders").select("*").eq("seller_email", email).execute()
    orders = orders_resp.data if orders_resp.data else []

    total_sales = sum(o['quantity'] for o in orders)
    delivered_orders = sum(1 for o in orders if o['delivered'])
    pending_orders = sum(1 for o in orders if not o['delivered'])

    # Best-selling products
    best_selling = {}
    for o in orders:
        pname = o['product_name']
        best_selling[pname] = best_selling.get(pname, 0) + o['quantity']
    best_selling_products = sorted(best_selling.items(), key=lambda x: x[1], reverse=True)[:3]

    return render_template("dashboard.html", profile=profile_data, notifications=notifications,
                           total_sales=total_sales, delivered_orders=delivered_orders,
                           pending_orders=pending_orders, best_selling_products=best_selling_products)

# ---------------------
# Run app
# ---------------------
if __name__ == '__main__':
    app.run(debug=True, port=2008)
