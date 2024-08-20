from flask import Flask, jsonify, render_template, redirect, session, url_for, request, flash
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
import bcrypt

app = Flask(__name__)
app.config['MONGO_URI'] = "mongodb://localhost:27017/instant_mart_db"
mongo = PyMongo(app)

app.secret_key = 'instant_mart_key'

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = mongo.db.users
        user = users.find_one({'email': request.form['email']})

        if user and bcrypt.checkpw(request.form['password'].encode('utf-8'), user['password']):
            session['email'] = user['email']
            flash('Welcome, ' + session['email'],'info')
            return redirect(url_for('home'))

        flash('Invalid email/password.','error')
        return redirect(url_for('login'))

    return render_template('login.html')

@app.route("/signup", methods=['POST', 'GET'])
def signup():
    if request.method == 'POST':
        users = mongo.db.users
        existing_user = users.find_one({'email': request.form['email']})
        password = request.form['password']
        repassword = request.form['repassword']

        if existing_user:
            flash(request.form['email'] + ' email is already registered.','error')
            return redirect(url_for('signup'))

        elif password != repassword:
            flash('No match with passwords.','error')
            return redirect(url_for('signup'))

        hashed_pw = bcrypt.hashpw(request.form['password'].encode('utf-8'), bcrypt.gensalt())
        users.insert_one({
            'email': request.form['email'],
            'password': hashed_pw
        })
        flash('Registration successful. Please log in.','info')
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/home')
def home():
    if 'email' in session:
        cart_items = mongo.db.carts.find({'user_id': session['email']})
        cart_dict = {str(item['product_id']): item['quantity'] for item in cart_items}
        cart_count = mongo.db.carts.count_documents({'user_id': session['email']})
    else:
        cart_dict = {}

    products = mongo.db.products.find()
    product_list = []

    for product in products:
        product_id = str(product['_id'])
        if product_id in cart_dict:
            product['in_cart'] = True
            product['quantity'] = cart_dict[product_id]
        else:
            product['in_cart'] = False
            product['quantity'] = 0
        product_list.append(product)

    return render_template('home.html', products=product_list, username=session['email'], cart_count=cart_count)

@app.route('/update_cart_quantity/<product_id>')
def update_cart_quantity(product_id):
    if 'email' not in session:
        flash('Please log in to update your cart.', 'error')
        return redirect(url_for('login'))

    change = int(request.args.get('change', 1))
    
    cart = mongo.db.carts.find_one({'user_id': session['email'], 'product_id': ObjectId(product_id)})
    if cart:
        new_quantity = cart['quantity'] + change
        if new_quantity > 0:
            mongo.db.carts.update_one({'_id': cart['_id']}, {'$set': {'quantity': new_quantity}})
        else:
            mongo.db.carts.delete_one({'_id': cart['_id']})
            flash('Product removed from cart.', 'error')
    else:
        if change > 0:
            mongo.db.carts.insert_one({
                'user_id': session['email'],
                'product_id': ObjectId(product_id),
                'quantity': change
            })
            flash('Product added to cart.', 'info')
    
    return redirect(request.referrer)

@app.route('/cart')
def cart():
    if 'email' not in session:
        flash('Please log in to view your cart.','error')
        return redirect(url_for('login'))

    cart_count = mongo.db.carts.count_documents({'user_id': session['email']})
    cart_items = mongo.db.carts.find({'user_id': session['email']})
    products = []
    total_price = 0
    hand_fee = 5
    del_fee = 16
    pay_amt = 0
    for item in cart_items:
        product = mongo.db.products.find_one({'_id': item['product_id']})
        if product:
            product['quantity'] = item['quantity']
            product['total'] = product['price'] * item['quantity']
            product['cart_item_id'] = str(item['_id'])
            total_price += product['total']
            products.append(product)
            pay_amt = total_price + hand_fee + del_fee

    return render_template('cart.html', products=products, total_price=total_price, pay_amt=pay_amt, username=session['email'], cart_count=cart_count)



@app.route('/place_order', methods=['GET', 'POST'])
def place_order():
    if 'email' not in session:
        flash('Please log in to place an order.')
        return redirect(url_for('login'))

    cart_count = mongo.db.carts.count_documents({'user_id': session['email']})

    if cart_count == 0:
        flash('Your cart is empty!')
        return redirect(url_for('home'))

    cart_items = mongo.db.carts.find({'user_id': session['email']})
    
    total_price = 0
    hand_fee = 5
    del_fee = 16
    
    order_items = []
    
    for item in cart_items:
        product = mongo.db.products.find_one({'_id': item['product_id']})
        if product:
            item_total = product['price'] * item['quantity']
            total_price += item_total
            order_items.append({
                'product_id': item['product_id'],
                'quantity': item['quantity'],
                'item_total': item_total
            })

    total_price += hand_fee + del_fee
    
    order = {
        'user_id': session['email'],
        'items': order_items,
        'total_price': total_price,
        'order_status': 'Success'
    }

    mongo.db.orders.insert_one(order)
    mongo.db.carts.delete_many({'user_id': session['email']})
    flash('Order placed successfully!', 'info')

    return redirect(url_for('home'))


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('email', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


if __name__ == "__main__":
    app.run(debug=True)
