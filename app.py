from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from supabase import create_client, Client
import qrcode
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for session management

# ---------------- Supabase Setup ----------------
SUPABASE_URL = "https://hdzblqzidgwaqbaqyyaz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhkemJscXppZGd3YXFiYXF5eWF6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc0MjIxNTYsImV4cCI6MjA3Mjk5ODE1Nn0.G2cXOescsoOej5eNzrJzTkVCyjpbVPNhx8UeXM_HPrA"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- Helpers ----------------
def get_notifications():
    return session.get('notifications', [])

def add_notification(msg):
    notes = session.get('notifications', [])
    notes.append(msg)
    session['notifications'] = notes

def clear_notifications():
    session['notifications'] = []

# ---------------- Routes ----------------
@app.route("/")
def root():
    return redirect(url_for('welcome'))

@app.route("/welcome")
def welcome():
    return render_template("welcome.html")

@app.route("/shop")
def index():
    products = supabase.table("products").select("*").execute().data
    return render_template("index.html", data=products)

@app.route("/add")
def add():
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
    product_name = request.form['product_name']
    product_price = request.form['product_price']
    stock = request.form['stock']
    image_path = request.files['product_image']
    image_name = image_path.filename
    image_path.save(f"static/images/{image_name}")
    supabase.table("products").insert({
        "product_name": product_name,
        "product_price": product_price,
        "stock": stock,
        "seller_email": email,
        "image_path": image_name
    }).execute()
    products = supabase.table("products").select("*").eq("seller_email", email).execute().data
    return render_template("add.html", data=products)

@app.route("/buy_product", methods=['POST'])
def buy_product():
    product_name = request.form['product_name']
    product_price = request.form['product_price']
    image_path = request.form['image_path']
    buyer_name = request.form['buyer_name']
    buyer_email = request.form['buyer_email']
    buyer_phone = request.form['buyer_phone']
    buyer_address = request.form['buyer_address']
    quantity = int(request.form['quantity'])

    # Get product & seller
    products = supabase.table("products").select("*").eq("product_name", product_name).eq("image_path", image_path).execute().data
    if not products:
        return jsonify({"error": "Product not found"}), 404
    product = products[0]
    seller_email = product['seller_email']

    # Add order
    supabase.table("orders").insert({
        "product_id": product['id'],
        "buyer_name": buyer_name,
        "buyer_email": buyer_email,
        "buyer_phone": buyer_phone,
        "buyer_address": buyer_address,
        "quantity": quantity,
        "seller_email": seller_email,
        "status": "pending"
    }).execute()

    # Update stock
    new_stock = int(product['stock']) - quantity
    if new_stock <= 0:
        supabase.table("products").delete().eq("id", product['id']).execute()
    else:
        supabase.table("products").update({"stock": new_stock}).eq("id", product['id']).execute()

    add_notification(f"New order from {buyer_name} for {product_name} (Qty: {quantity})")
    return jsonify({'status': 'success'})

@app.route("/orders")
def orders():
    if not session.get('seller_logged_in'):
        return redirect(url_for('seller_login'))
    email = session.get('seller_email')
    orders = supabase.table("orders").select("*").eq("seller_email", email).execute().data
    return render_template("orders.html", orders=orders)

@app.route("/seller_register", methods=["GET", "POST"])
def seller_register():
    error = None
    if request.method == "POST":
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']

        # Check existing seller
        existing = supabase.table("sellers").select("*").eq("email", email).execute().data
        if existing:
            error = "Email already registered."
        else:
            supabase.table("sellers").insert({
                "name": name,
                "email": email,
                "phone": phone,
                "password": password
            }).execute()
            session['seller_logged_in'] = True
            session['seller_email'] = email
            return redirect(url_for('index'))

    return render_template("seller_register.html", error=error)

@app.route("/seller_login", methods=["GET", "POST"])
def seller_login():
    error = None
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']
        seller = supabase.table("sellers").select("*").eq("email", email).eq("password", password).execute().data
        if seller:
            session['seller_logged_in'] = True
            session['seller_email'] = email
            return redirect(url_for('index'))
        else:
            error = "Invalid credentials."
    return render_template("seller_login.html", error=error)

# ---------------- Run App ----------------
if __name__ == "__main__":
    app.run(debug=True, port=2008)
