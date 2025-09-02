from flask import Flask, jsonify, render_template, redirect, url_for, request, send_from_directory, flash, session, send_file
import os,json
from werkzeug.utils import secure_filename
from datetime import datetime
import qrcode
from flask_sqlalchemy import SQLAlchemy

app=Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for session management

# Database setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Seller model
class Seller(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    image_path = db.Column(db.String(200))
    # ... add other fields as needed ...

# Product model
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_path = db.Column(db.String(200))
    product_name = db.Column(db.String(120), nullable=False)
    product_price = db.Column(db.String(20), nullable=False)
    stock = db.Column(db.String(10), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('seller.id'), nullable=False)
    seller = db.relationship('Seller', backref=db.backref('products', lazy=True))

# Order model
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    product = db.relationship('Product', backref=db.backref('orders', lazy=True))
    buyer_name = db.Column(db.String(120))
    buyer_phone = db.Column(db.String(20))
    buyer_email = db.Column(db.String(120))
    buyer_address = db.Column(db.String(200))
    quantity = db.Column(db.Integer)
    seller_id = db.Column(db.Integer, db.ForeignKey('seller.id'), nullable=False)
    seller = db.relationship('Seller', backref=db.backref('orders', lazy=True))

# Helper for notifications (simple session-based for demo)
def get_notifications():
    return session.get('notifications', [])
def add_notification(msg):
    notes = session.get('notifications', [])
    notes.append(msg)
    session['notifications'] = notes

def clear_notifications():
    session['notifications'] = []

@app.route("/")
def root():
    return redirect(url_for('welcome'))

@app.route("/shop")
def index():
    if os.path.exists("base.json"):
        try:
         with open ("base.json") as file:
            data=json.load(file)
            
        except:
           data=[]
    else:
       data=[]
    return render_template("index.html",data=data)
@app.route("/add")
def get():
    if not session.get('seller_logged_in'):
        return redirect(url_for('seller_login'))
    email = session.get('seller_email')
    products = []
    if os.path.exists("base.json"):
        try:
            with open ("base.json") as file:
                all_products = json.load(file)
            products = [p for p in all_products if p.get('seller_email') == email]
        except:
            products = []
    return render_template("add.html", data=products)
@app.route("/add_product",methods=['POST'])
def product_info():
    if not session.get('seller_logged_in'):
        return redirect(url_for('seller_login'))
    email = session.get('seller_email')
    image_path=request.files['product_image']
    product_name=request.form['product_name']
    product_price=request.form['product_price']
    stock=request.form['stock']
    images_dir = os.path.join('static', 'images')
    os.makedirs(images_dir, exist_ok=True)
    image_name = secure_filename(image_path.filename)
    image_path.save(os.path.join(images_dir, image_name))
    info = {
        "image_path": image_name,
        "product_name": product_name,
        "product_price": product_price,
        "stock": stock,
        "seller_email": email
    }
    data = []
    if os.path.exists("base.json"):
        try:
            with open ("base.json") as file:
                data=json.load(file)
        except:
           data=[]
    data.append(info)
    with open('base.json', 'w') as file:
        json.dump(data, file, indent=4)
    # Only show this seller's products after add
    products = [p for p in data if p.get('seller_email') == email]
    return render_template("add.html",data=products)
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
    # Find the seller_email for this product
    seller_email = None
    if os.path.exists('base.json'):
        with open('base.json') as f:
            products = json.load(f)
        for p in products:
            if p['product_name'] == product_name and p['image_path'] == image_path:
                seller_email = p.get('seller_email')
                break
    order = {
        'product_name': product_name,
        'product_price': product_price,
        'image_path': image_path,
        'buyer_name': buyer_name,
        'buyer_phone': buyer_phone,
        'buyer_email': buyer_email,
        'buyer_address': buyer_address,
        'quantity': quantity,
        'seller_email': seller_email
    }
    orders = []
    if os.path.exists('orders.json'):
        try:
            with open('orders.json') as f:
                orders = json.load(f)
        except:
            orders = []
    orders.append(order)
    with open('orders.json', 'w') as f:
        json.dump(orders, f, indent=4)
    # Update stock in base.json
    products = []
    if os.path.exists('base.json'):
        try:
            with open('base.json') as f:
                products = json.load(f)
        except:
            products = []
    for p in products[:]:
        if p['product_name'] == product_name and p['image_path'] == image_path:
            try:
                p['stock'] = int(p['stock']) - quantity
            except:
                p['stock'] = 0
            if p['stock'] <= 0:
                products.remove(p)
    with open('base.json', 'w') as f:
        json.dump(products, f, indent=4)
    add_notification(f"New order from {buyer_name} for {product_name} (Qty: {quantity})")
    return jsonify({'status': 'success', 'product': order})

@app.route("/receipt/<int:order_id>")
def make_receipt(order_id):
    orders = []
    if os.path.exists('orders.json'):
        try:
            with open('orders.json') as f:
                orders = json.load(f)
        except:
            orders = []
    if 0 <= order_id < len(orders):
        order = orders[order_id]
        # Generate unique number (00001, 00002, ...)
        unique_number = str(order_id + 1).zfill(5)
        # Timestamp
        timestamp = order.get('timestamp')
        if not timestamp:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            order['timestamp'] = timestamp
            orders[order_id] = order
            with open('orders.json', 'w') as f:
                json.dump(orders, f, indent=4)
        # Generate QR code (with order info)
        qr_data = f"Receipt #{unique_number}\nBuyer: {order['buyer_name']}\nItem: {order['product_name']}\nQty: {order['quantity']}\nPaid: {order['product_price']}\nTime: {timestamp}"
        qr = qrcode.make(qr_data)
        qr_path = f'static/images/qr_{unique_number}.png'
        qr.save(qr_path)
        return render_template('receipt.html', order=order, order_id=order_id, unique_number=unique_number, timestamp=timestamp, qr_path=qr_path)
    return 'Order not found', 404

@app.route("/orders", methods=["GET", "POST"])
def show_orders():
    if not session.get('seller_logged_in'):
        return redirect(url_for('seller_login'))
    email = session.get('seller_email')
    orders = []
    if os.path.exists('orders.json'):
        try:
            with open('orders.json') as f:
                all_orders = json.load(f)
            orders = [o for o in all_orders if o.get('seller_email') == email]
        except:
            orders = []
    search_query = request.args.get('search', '').strip().lower()
    filter_status = request.args.get('status', '')
    filtered_orders = orders
    if search_query:
        filtered_orders = [o for o in filtered_orders if search_query in o.get('buyer_name','').lower() or search_query in o.get('product_name','').lower()]
    if filter_status == 'pending':
        filtered_orders = [o for o in filtered_orders if not o.get('delivered')]
    elif filter_status == 'delivered':
        filtered_orders = [o for o in filtered_orders if o.get('delivered')]
    # Mark as delivered
    if request.method == "POST":
        order_id = int(request.form.get('order_id', -1))
        if 0 <= order_id < len(orders):
            orders[order_id]['delivered'] = True
            with open('orders.json', 'w') as f:
                json.dump(all_orders, f, indent=4)
    return render_template("orders.html", orders=filtered_orders, search_query=search_query, filter_status=filter_status)

@app.route("/check_delivery", methods=["GET", "POST"])
def check_delivery():
    status = None
    if request.method == "POST":
        receipt = request.form.get('receipt', '').strip()
        if receipt.isdigit():
            order_id = int(receipt) - 1
            orders = []
            if os.path.exists('orders.json'):
                try:
                    with open('orders.json') as f:
                        orders = json.load(f)
                except:
                    orders = []
            if 0 <= order_id < len(orders):
                status = 'delivered' if orders[order_id].get('delivered') else 'pending'
            else:
                status = 'notfound'
        else:
            status = 'notfound'
    return render_template('check_delivery.html', status=status)
@app.route("/dashboard")
def dashboard():
    if not session.get('seller_logged_in'):
        return redirect(url_for('seller_login'))
    email = session.get('seller_email')
    sellers = []
    profile_data = {}
    if os.path.exists('sellers.json'):
        with open('sellers.json') as f:
            sellers = json.load(f)
        profile_data = next((s for s in sellers if s['email'] == email), {})
    notifications = get_notifications()
    clear_notifications()
    # --- Sales Analytics ---
    total_sales = 0
    delivered_orders = 0
    pending_orders = 0
    best_selling = {}
    if os.path.exists('orders.json'):
        try:
            with open('orders.json') as f:
                all_orders = json.load(f)
            orders = [o for o in all_orders if o.get('seller_email') == email]
            for order in orders:
                qty = int(order.get('quantity', 1))
                total_sales += qty
                if order.get('delivered'):
                    delivered_orders += 1
                else:
                    pending_orders += 1
                pname = order.get('product_name')
                if pname:
                    best_selling[pname] = best_selling.get(pname, 0) + qty
        except:
            pass
    best_selling_products = sorted(best_selling.items(), key=lambda x: x[1], reverse=True)[:3]
    return render_template("dashboard.html", profile=profile_data, notifications=notifications,
        total_sales=total_sales, delivered_orders=delivered_orders, pending_orders=pending_orders,
        best_selling_products=best_selling_products)

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if not session.get('seller_logged_in'):
        return redirect(url_for('seller_login'))
    email = session.get('seller_email')
    sellers = []
    profile_data = {}
    if os.path.exists('sellers.json'):
        with open('sellers.json') as f:
            sellers = json.load(f)
        profile_data = next((s for s in sellers if s['email'] == email), {})
    message = None
    if request.method == "POST":
        # Update only this seller's profile
        for s in sellers:
            if s['email'] == email:
                s['name'] = request.form.get('name', s['name'])
                s['email'] = request.form.get('email', s['email'])
                s['phone'] = request.form.get('phone', s['phone'])
                if 'profile_pic' in request.files and request.files['profile_pic'].filename:
                    pic = request.files['profile_pic']
                    filename = secure_filename(pic.filename)
                    img_path = os.path.join('static', 'images', 'profile', filename)
                    pic.save(img_path)
                    s['image_url'] = url_for('static', filename=f'images/profile/{filename}')
                profile_data = s
                break
        with open('sellers.json', 'w') as f:
            json.dump(sellers, f, indent=4)
        message = "Profile updated successfully!"
    return render_template("profile.html", profile=profile_data, message=message)

@app.route("/profile/change_password", methods=["POST"])
def change_password():
    if os.path.exists('profile.json'):
        with open('profile.json') as f:
            profile_data = json.load(f)
    else:
        return redirect(url_for('profile'))
    old = request.form.get('old_password')
    new = request.form.get('new_password')
    confirm = request.form.get('confirm_password')
    message = None
    if old != profile_data.get('password'):
        message = "Old password is incorrect."
    elif new != confirm:
        message = "New passwords do not match."
    elif not new or len(new) < 4:
        message = "New password must be at least 4 characters."
    else:
        profile_data['password'] = new
        with open('profile.json', 'w') as f:
            json.dump(profile_data, f, indent=4)
        message = "Password changed successfully!"
    return render_template("profile.html", profile=profile_data, message=message)

@app.route("/edit_product/<int:idx>", methods=["GET", "POST"])
def edit_product(idx):
    products = []
    if os.path.exists('base.json'):
        with open('base.json') as f:
            products = json.load(f)
    if idx < 0 or idx >= len(products):
        return redirect(url_for('get'))
    if request.method == "POST":
        products[idx]['product_name'] = request.form.get('product_name', products[idx]['product_name'])
        products[idx]['product_price'] = request.form.get('product_price', products[idx]['product_price'])
        products[idx]['stock'] = request.form.get('stock', products[idx]['stock'])
        # Optional: handle image update
        if 'product_image' in request.files and request.files['product_image'].filename:
            image = request.files['product_image']
            image_name = secure_filename(image.filename)
            image.save(os.path.join('static', 'images', image_name))
            products[idx]['image_path'] = image_name
        with open('base.json', 'w') as f:
            json.dump(products, f, indent=4)
        return redirect(url_for('get'))
    return render_template('edit_product.html', product=products[idx], idx=idx)

@app.route("/delete_product/<int:idx>", methods=["POST"])
def delete_product(idx):
    products = []
    if os.path.exists('base.json'):
        with open('base.json') as f:
            products = json.load(f)
    if 0 <= idx < len(products):
        products.pop(idx)
        with open('base.json', 'w') as f:
            json.dump(products, f, indent=4)
    return redirect(url_for('get'))

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
            sellers = []
            if os.path.exists('sellers.json'):
                with open('sellers.json') as f:
                    sellers = json.load(f)
            # Check if email already exists
            if any(s['email'] == email for s in sellers):
                error = "Email already registered. Please login."
            else:
                new_seller = {
                    'name': name,
                    'email': email,
                    'phone': phone,
                    'role': 'Seller',
                    'image_url': url_for('static', filename='images/default-profile.png'),
                    'password': password
                }
                sellers.append(new_seller)
                with open('sellers.json', 'w') as f:
                    json.dump(sellers, f, indent=4)
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
        sellers = []
        if os.path.exists('sellers.json'):
            with open('sellers.json') as f:
                sellers = json.load(f)
        seller = next((s for s in sellers if s['email'] == email and s['password'] == password), None)
        if seller:
            session['seller_logged_in'] = True
            session['seller_email'] = email
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid email or password."
    return render_template("seller_login.html", error=error)

@app.route('/migrate_json_to_db')
def migrate_json_to_db():
    # Migrate sellers
    sellers_path = 'sellers.json'
    if os.path.exists(sellers_path):
        with open(sellers_path) as f:
            sellers = json.load(f)
        for s in sellers:
            if not Seller.query.filter_by(email=s['email']).first():
                seller = Seller(
                    name=s.get('name', ''),
                    email=s.get('email', ''),
                    password=s.get('password', ''),
                    phone=s.get('phone', ''),
                    address=s.get('address', ''),
                    image_path=s.get('image_url', '')
                )
                db.session.add(seller)
        db.session.commit()
    # Migrate products
    products_path = 'base.json'
    if os.path.exists(products_path):
        with open(products_path) as f:
            products = json.load(f)
        for p in products:
            seller = Seller.query.filter_by(email=p.get('seller_email')).first()
            if seller:
                product = Product(
                    image_path=p.get('image_path', ''),
                    product_name=p.get('product_name', ''),
                    product_price=p.get('product_price', ''),
                    stock=p.get('stock', ''),
                    seller_id=seller.id
                )
                db.session.add(product)
        db.session.commit()
    # Migrate orders
    orders_path = 'orders.json'
    if os.path.exists(orders_path):
        with open(orders_path) as f:
            orders = json.load(f)
        for o in orders:
            seller = Seller.query.filter_by(email=o.get('seller_email')).first()
            product = Product.query.filter_by(product_name=o.get('product_name')).first()
            if seller and product:
                order = Order(
                    product_id=product.id,
                    buyer_name=o.get('buyer_name', ''),
                    buyer_phone=o.get('buyer_phone', ''),
                    buyer_email=o.get('buyer_email', ''),
                    buyer_address=o.get('buyer_address', ''),
                    quantity=o.get('quantity', 1),
                    seller_id=seller.id
                )
                db.session.add(order)
        db.session.commit()
    return 'Migration complete! You can now remove this route for security.'

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # This will create the tables if they don't exist
    app.run(debug=True,port=2008)