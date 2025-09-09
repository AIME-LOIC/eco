from flask import Flask, jsonify, render_template, redirect, url_for, request, session
from werkzeug.utils import secure_filename
from datetime import datetime
import os, qrcode
from supabase import create_client, Client

# --- Flask setup ---
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# --- Supabase setup ---
SUPABASE_URL = "https://hdzblqzidgwaqbaqyyaz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhkemJscXppZGd3YXFiYXF5eWF6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc0MjIxNTYsImV4cCI6MjA3Mjk5ODE1Nn0.G2cXOescsoOej5eNzrJzTkVCyjpbVPNhx8UeXM_HPrA"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Helper functions for notifications ---
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
        return redirect(url_for('shop'))
    elif role == 'seller':
        return redirect(url_for('seller_login'))
    return redirect(url_for('welcome'))

# --- Seller Registration ---
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
            if existing.data and len(existing.data) > 0:
                error = "Email already registered. Please login."
            else:
                supabase.table("sellers").insert({
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "password": password,
                    "role": "Seller",
                    "image_url": "/static/images/default-profile.png"
                }).execute()
                session['seller_logged_in'] = True
                session['seller_email'] = email
                return redirect(url_for('dashboard'))
    return render_template("seller_register.html", error=error)

# --- Seller Login ---
@app.route("/seller_login", methods=["GET", "POST"])
def seller_login():
    error = None
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        result = supabase.table("sellers").select("*").eq("email", email).eq("password", password).execute()
        if result.data and len(result.data) > 0:
            session['seller_logged_in'] = True
            session['seller_email'] = email
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid email or password."
    return render_template("seller_login.html", error=error)

# --- Dashboard ---
@app.route("/dashboard")
def dashboard():
    if not session.get('seller_logged_in'):
        return redirect(url_for('seller_login'))
    email = session.get('seller_email')
    seller_data = supabase.table("sellers").select("*").eq("email", email).execute().data[0]

    # Fetch seller's orders
    all_orders = supabase.table("orders").select("*").eq("seller_email", email).execute().data
    total_sales = sum([o['quantity'] for o in all_orders]) if all_orders else 0
    delivered_orders = sum([1 for o in all_orders if o.get('delivered')]) if all_orders else 0
    pending_orders = sum([1 for o in all_orders if not o.get('delivered')]) if all_orders else 0

    # Best-selling products
    best_selling = {}
    if all_orders:
        for o in all_orders:
            pname = o.get('product_name')
            if pname:
                best_selling[pname] = best_selling.get(pname, 0) + o['quantity']
    best_selling_products = sorted(best_selling.items(), key=lambda x: x[1], reverse=True)[:3]

    notifications = get_notifications()
    clear_notifications()

    return render_template("dashboard.html", profile=seller_data, notifications=notifications,
                           total_sales=total_sales, delivered_orders=delivered_orders,
                           pending_orders=pending_orders, best_selling_products=best_selling_products)

# --- Shop / Buyer view ---
@app.route("/shop")
def shop():
    products = supabase.table("products").select("*").execute().data
    return render_template("index.html", data=products)

# --- Add Product ---
@app.route("/add", methods=["GET", "POST"])
def add_product():
    if not session.get('seller_logged_in'):
        return redirect(url_for('seller_login'))
    email = session.get('seller_email')
    if request.method == "POST":
        product_name = request.form['product_name']
        product_price = request.form['product_price']
        stock = request.form['stock']
        image_file = request.files['product_image']
        os.makedirs('static/images', exist_ok=True)
        image_name = secure_filename(image_file.filename)
        image_file.save(os.path.join('static/images', image_name))
        supabase.table("products").insert({
            "product_name": product_name,
            "product_price": product_price,
            "stock": stock,
            "seller_email": email,
            "image_path": f"/static/images/{image_name}"
        }).execute()
        return redirect(url_for('add_product'))
    # GET
    products = supabase.table("products").select("*").eq("seller_email", email).execute().data
    return render_template("add.html", data=products)

# --- Buy Product ---
@app.route("/buy_product", methods=["POST"])
def buy_product():
    product_name = request.form['product_name']
    quantity = int(request.form['quantity'])
    buyer_name = request.form['buyer_name']
    buyer_email = request.form['buyer_email']
    buyer_phone = request.form['buyer_phone']
    buyer_address = request.form['buyer_address']

    product = supabase.table("products").select("*").eq("product_name", product_name).execute().data[0]
    seller_email = product['seller_email']

    # Save order
    order_data = {
        "product_name": product_name,
        "product_price": product['product_price'],
        "quantity": quantity,
        "buyer_name": buyer_name,
        "buyer_email": buyer_email,
        "buyer_phone": buyer_phone,
        "buyer_address": buyer_address,
        "seller_email": seller_email,
        "image_path": product['image_path'],
        "delivered": False,
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    supabase.table("orders").insert(order_data).execute()

    # Update stock
    new_stock = max(int(product['stock']) - quantity, 0)
    supabase.table("products").update({"stock": new_stock}).eq("product_name", product_name).execute()

    add_notification(f"New order from {buyer_name} for {product_name} (Qty: {quantity})")
    return jsonify({"status": "success", "product": order_data})

# --- Run app ---
if __name__ == "__main__":
    app.run(debug=True, port=2008)
