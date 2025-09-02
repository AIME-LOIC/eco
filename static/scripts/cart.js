// cart.js

function updateCartCount() {
    const cart = JSON.parse(localStorage.getItem('cart') || '[]');
    document.getElementById('cart-count').textContent = cart.length;
}

function renderCartItems() {
    const cart = JSON.parse(localStorage.getItem('cart') || '[]');
    const cartItemsDiv = document.getElementById('cartItems');
    if (cart.length === 0) {
        cartItemsDiv.innerHTML = '<p>Your cart is empty.</p>';
        return;
    }
    cartItemsDiv.innerHTML = '';
    cart.forEach((product, idx) => {
        const div = document.createElement('div');
        div.className = 'cart-product';
        div.innerHTML = `
            <img src="/static/images/${product.image_path}" alt="" height="80px" style="margin-bottom:10px;">
            <div class="cart-product-info">
                <b>${product.product_name}</b><br>
                Price: ${product.product_price}<br>
            </div>
            <button class="cart-buy-btn" data-idx="${idx}">Buy</button>
            <button class="cart-remove" data-idx="${idx}">Remove</button>
        `;
        cartItemsDiv.appendChild(div);
    });
    // Add event listeners for remove and buy
    document.querySelectorAll('.cart-remove').forEach(btn => {
        btn.onclick = function() {
            const idx = parseInt(this.getAttribute('data-idx'));
            let cart = JSON.parse(localStorage.getItem('cart') || '[]');
            cart.splice(idx, 1);
            localStorage.setItem('cart', JSON.stringify(cart));
            updateCartCount();
            renderCartItems();
        };
    });
    document.querySelectorAll('.cart-buy-btn').forEach(btn => {
        btn.onclick = function() {
            const idx = parseInt(this.getAttribute('data-idx'));
            const cart = JSON.parse(localStorage.getItem('cart') || '[]');
            if (cart[idx]) {
                showBuyModal(cart[idx]);
            }
        };
    });
}

function showBuyModal(product) {
    const modal = document.getElementById('buyModal');
    const modalProductInfo = document.getElementById('modalProductInfo');
    const modalProductName = document.getElementById('modalProductName');
    const modalProductPrice = document.getElementById('modalProductPrice');
    const modalImagePath = document.getElementById('modalImagePath');
    modalProductInfo.innerHTML = `
        <img src="/static/images/${product.image_path}" height="80" style="margin-bottom:10px;"><br>
        <b>${product.product_name}</b><br>
        Price: ${product.product_price}<br>
        Stock: ${product.stock}
    `;
    modalProductName.value = product.product_name;
    modalProductPrice.value = product.product_price;
    modalImagePath.value = product.image_path;
    modal.style.display = 'block';
}

document.addEventListener('DOMContentLoaded', function() {
    updateCartCount();
    const modal = document.getElementById('buyModal');
    const closeBtns = document.querySelectorAll('.close');
    const cartModal = document.getElementById('cartModal');
    const cartIcon = document.getElementById('cartIcon');
    // Add to cart buttons
    document.querySelectorAll('.add-to-cart').forEach(btn => {
        btn.addEventListener('click', function() {
            const product = JSON.parse(this.getAttribute('data-product'));
            let cart = JSON.parse(localStorage.getItem('cart') || '[]');
            cart.push(product);
            localStorage.setItem('cart', JSON.stringify(cart));
            updateCartCount();
        });
    });
    // Cart icon click
    cartIcon.onclick = function() {
        renderCartItems();
        cartModal.style.display = 'block';
    };
    // Close modals
    closeBtns.forEach(btn => {
        btn.onclick = function() {
            this.closest('.modal').style.display = 'none';
        };
    });
    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
        if (event.target == cartModal) {
            cartModal.style.display = 'none';
        }
    };
    // Image preview modal logic
    const imagePreviewModal = document.getElementById('imagePreviewModal');
    const previewImg = document.getElementById('previewImg');
    const closeImagePreview = document.getElementById('closeImagePreview');
    document.querySelectorAll('.card img').forEach(img => {
        img.style.cursor = 'zoom-in';
        img.onclick = function(e) {
            previewImg.src = this.src;
            imagePreviewModal.classList.add('active');
        };
    });
    closeImagePreview.onclick = function() {
        imagePreviewModal.classList.remove('active');
        previewImg.src = '';
    };
    imagePreviewModal.onclick = function(e) {
        if (e.target === imagePreviewModal) {
            imagePreviewModal.classList.remove('active');
            previewImg.src = '';
        }
    };
    // Handle buy form AJAX
    const buyForm = document.getElementById('buyForm');
    if (buyForm) {
        buyForm.onsubmit = async function(e) {
            e.preventDefault();
            const formData = new FormData(buyForm);
            const productName = formData.get('product_name');
            const imagePath = formData.get('image_path');
            const response = await fetch('/buy_product', {
                method: 'POST',
                body: formData
            });
            if (response.ok) {
                // Remove bought product from cart
                let cart = JSON.parse(localStorage.getItem('cart') || '[]');
                cart = cart.filter(p => !(p.product_name === productName && p.image_path === imagePath));
                localStorage.setItem('cart', JSON.stringify(cart));
                updateCartCount();
                // Hide buy modal
                document.getElementById('buyModal').style.display = 'none';
                // Show success popup
                showBuySuccess();
            } else {
                alert('There was a problem with your order.');
            }
        };
    }
    // Show buy success popup
    function showBuySuccess() {
        let div = document.createElement('div');
        div.id = 'buySuccessPopup';
        div.style.position = 'fixed';
        div.style.top = '0';
        div.style.left = '0';
        div.style.width = '100vw';
        div.style.height = '100vh';
        div.style.background = 'rgba(0,0,0,0.7)';
        div.style.display = 'flex';
        div.style.alignItems = 'center';
        div.style.justifyContent = 'center';
        div.style.zIndex = '4000';
        div.innerHTML = `<div style="background:#fff;padding:32px 24px;border-radius:14px;max-width:90vw;text-align:center;box-shadow:0 4px 32px #0003;">
            <h2 style='color:#28a745;margin-bottom:12px;'>Thank you for your purchase!</h2>
            <p>Your order has been received. We will contact you soon.</p>
            <button style='margin-top:18px;padding:10px 24px;background:#007bff;color:#fff;border:none;border-radius:8px;font-size:1.1rem;cursor:pointer;' onclick='document.getElementById("buySuccessPopup").remove()'>Close</button>
        </div>`;
        document.body.appendChild(div);
    }
});
