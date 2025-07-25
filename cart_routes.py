from flask import Blueprint, session, redirect, url_for, request, flash, render_template, jsonify
from models import Product, db  # Adjust import if Product is elsewhere
from functools import wraps

cart_bp = Blueprint('cart', __name__)


def get_cart_count():
    """Helper function to get total items in cart"""
    cart = session.get('cart', {})
    return sum(cart.values())


def init_cart():
    """Initialize cart in session if it doesn't exist"""
    if 'cart' not in session:
        session['cart'] = {}
    return session['cart']


# Add to cart
@cart_bp.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    try:
        cart = init_cart()
        # Get product and validate it exists
        product = Product.query.get_or_404(product_id)

        # Get requested quantity, default to 1
        quantity = int(request.form.get('quantity', 1))
        if quantity < 1:
            flash('Invalid quantity specified.', 'error')
            return redirect(request.referrer or url_for('home'))

        # Check if product is active
        if not product.is_active:
            flash('This product is currently not available.', 'error')
            return redirect(request.referrer or url_for('home'))

        # Get current cart
        current_quantity = cart.get(str(product_id), 0)
        new_quantity = current_quantity + quantity

        # Check stock availability
        if new_quantity > product.stock:
            flash(f'Sorry, only {product.stock} items available in stock.', 'error')
            return redirect(request.referrer or url_for('home'))

        # Update cart
        cart[str(product_id)] = new_quantity
        session['cart'] = cart
        session.modified = True
        flash('Product added to cart!', 'success')

        # If AJAX request, return JSON response
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'cart_count': get_cart_count(),
                'message': 'Product added to cart!'
            })

        return redirect(url_for('cart.view_cart'))

    except ValueError:
        flash('Invalid quantity specified.', 'error')
    except Exception as e:
        flash('An error occurred while adding to cart.', 'error')

    return redirect(request.referrer or url_for('home'))


# View cart
@cart_bp.route('/cart')
def view_cart():
    try:
        cart = init_cart()
        if not cart:
            return render_template('cart.html', cart_items=[], total=0)

        product_ids = [int(pid) for pid in cart.keys()]
        products = Product.query.filter(Product.id.in_(product_ids)).all() if product_ids else []

        # Validate cart items and remove invalid ones
        valid_cart = {}
        cart_items = []
        total = 0

        for product in products:
            if not product.is_active:
                flash(f'"{product.name}" has been removed from cart as it is no longer available.', 'warning')
                continue

            quantity = cart.get(str(product.id), 0)

            # Check if requested quantity is still in stock
            if quantity > product.stock:
                quantity = product.stock
                flash(f'Quantity for "{product.name}" has been adjusted to {product.stock} due to stock availability.',
                      'warning')

            if quantity > 0:
                valid_cart[str(product.id)] = quantity
                subtotal = float(product.price * quantity)
                cart_items.append({
                    'product': product,
                    'quantity': quantity,
                    'subtotal': subtotal
                })
                total += subtotal

        # Update cart if any items were removed
        if valid_cart != cart:
            session['cart'] = valid_cart
            session.modified = True

        return render_template('cart.html', cart_items=cart_items, total=total)

    except Exception as e:
        print(f"Cart error: {e}")  # Add logging for debugging
        flash('An error occurred while loading your cart.', 'error')
        return redirect(url_for('home'))


# Remove from cart
@cart_bp.route('/remove_from_cart/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    try:
        cart = init_cart()
        if str(product_id) in cart:
            del cart[str(product_id)]
            session['cart'] = cart
            session.modified = True
            flash('Product removed from cart!', 'success')

        # If AJAX request, return JSON response
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'cart_count': get_cart_count(),
                'message': 'Product removed from cart!'
            })

    except Exception as e:
        flash('An error occurred while removing the item.', 'error')

    return redirect(url_for('cart.view_cart'))


# Update quantity
@cart_bp.route('/update_cart/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    try:
        cart = init_cart()
        product = Product.query.get_or_404(product_id)
        quantity = int(request.form.get('quantity', 0))

        if quantity < 0:
            flash('Invalid quantity specified.', 'error')
            return redirect(url_for('cart.view_cart'))

        # Remove item if quantity is 0
        if quantity == 0:
            if str(product_id) in cart:
                del cart[str(product_id)]
                session['cart'] = cart
                session.modified = True
                flash('Product removed from cart!', 'success')
        else:
            # Check stock availability
            if quantity > product.stock:
                flash(f'Sorry, only {product.stock} items available in stock.', 'error')
                quantity = product.stock

            cart[str(product_id)] = quantity
            session['cart'] = cart
            session.modified = True
            flash('Cart updated!', 'success')

        # If AJAX request, return JSON response
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'cart_count': get_cart_count(),
                'message': 'Cart updated!'
            })

    except ValueError:
        flash('Invalid quantity specified.', 'error')
    except Exception as e:
        flash('An error occurred while updating the cart.', 'error')

    return redirect(url_for('cart.view_cart'))

