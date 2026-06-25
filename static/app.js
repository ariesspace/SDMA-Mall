const base = document.body.dataset.basePath;
let state = { products: [] };
let currentUser = null;
let cart = new Map();
let alienTapCount = 0;

const $ = (id) => document.getElementById(id);
const money = (value) => `${Number(value || 0).toLocaleString()} P`;

async function api(path, options = {}) {
  const response = await fetch(base + path, {
    ...options,
    headers: { "Content-Type": "application/json; charset=utf-8", ...(options.headers || {}) },
  });
  return response.json();
}

async function loadState() {
  state = await api("/api/state");
  renderProducts();
  renderCart();
}

function productById(id) {
  return state.products.find((product) => Number(product.id) === Number(id));
}

function discount(product) {
  if (!product.original_price || product.original_price <= product.price) return 0;
  return Math.round((1 - product.price / product.original_price) * 100);
}

function renderProducts() {
  $("productCount").textContent = state.products.length;
  $("products").innerHTML = state.products.map((product) => {
    const sale = discount(product);
    const image = product.image_url || "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=800&q=80";
    const stockText = product.stock === null ? "재고 충분" : `재고 ${product.stock}개`;
    return `
      <article class="product-card">
        <div class="product-image">
          ${sale ? `<span class="discount">-${sale}%</span>` : ""}
          <img src="${image}" alt="${product.name}">
        </div>
        <h3>${product.name}</h3>
        <p>${product.description || stockText}</p>
        <div class="price-row">
          <strong class="price">${money(product.price)}</strong>
          ${product.original_price > product.price ? `<span class="original-price">${money(product.original_price)}</span>` : ""}
        </div>
        <button class="pixel-button full" type="button" onclick="addToCart(${product.id})">담기</button>
      </article>
    `;
  }).join("") || `<p>등록된 상품이 없습니다.</p>`;
}

function renderCart() {
  let count = 0;
  let total = 0;
  const lines = [...cart.entries()].map(([id, quantity]) => {
    const product = productById(id);
    if (!product) return "";
    count += quantity;
    total += product.price * quantity;
    return `
      <div class="cart-line">
        <strong>${product.name}</strong>
        <p>${money(product.price)} × <input type="number" min="0" value="${quantity}" onchange="setCartQuantity(${id}, this.value)"></p>
        <b>${money(product.price * quantity)}</b>
      </div>
    `;
  }).join("");
  $("cartCount").textContent = count;
  $("cartItems").innerHTML = lines || `<p>장바구니가 비어 있습니다.</p>`;
  $("cartTotal").textContent = money(total);
}

function addToCart(id) {
  cart.set(Number(id), (cart.get(Number(id)) || 0) + 1);
  renderCart();
  $("cartDrawer").classList.remove("hidden");
}

function setCartQuantity(id, value) {
  const quantity = Math.max(0, Number(value || 0));
  if (quantity === 0) cart.delete(Number(id));
  else cart.set(Number(id), quantity);
  renderCart();
}

function showLogin() {
  $("loginMessage").textContent = "";
  $("loginDialog").showModal();
  setTimeout(() => $("employeeInput").focus(), 50);
}

async function login() {
  const employeeNo = $("employeeInput").value.trim();
  const result = await api("/api/login", { method: "POST", body: JSON.stringify({ employee_no: employeeNo }) });
  if (!result.ok) {
    $("loginMessage").textContent = result.message;
    return;
  }
  currentUser = result.user;
  $("loginDialog").close();
  $("intro").classList.add("hidden");
  $("mall").classList.remove("hidden");
  $("userChip").textContent = `${currentUser.team || "SDMA"} ${currentUser.name || currentUser.employee_no} / ${money(currentUser.points)}`;
  window.scrollTo(0, 0);
}

function formatReceipt(receipt) {
  const order = receipt.order;
  const lines = receipt.items.map((item) => {
    const subtotal = item.unit_price * item.quantity;
    return `${item.quantity}x ${item.product_name.padEnd(18, " ")} ${money(subtotal)}`;
  });
  return [
    "[ 영 수 증 ]",
    order.created_at,
    "--------------------------------",
    ...lines,
    "--------------------------------",
    `총 합계                 ${money(order.total_points)}`,
  ].join("\n");
}

async function checkout() {
  if (!currentUser) {
    showLogin();
    return;
  }
  const items = [...cart.entries()].map(([product_id, quantity]) => ({ product_id, quantity }));
  const result = await api("/api/checkout", {
    method: "POST",
    body: JSON.stringify({ user_id: currentUser.id, items }),
  });
  if (!result.ok) {
    $("cartMessage").textContent = result.message;
    return;
  }
  state = result.state;
  currentUser.points -= result.receipt.order.total_points;
  $("userChip").textContent = `${currentUser.team || "SDMA"} ${currentUser.name || currentUser.employee_no} / ${money(currentUser.points)}`;
  cart = new Map();
  renderProducts();
  renderCart();
  $("cartDrawer").classList.add("hidden");
  $("receiptText").textContent = formatReceipt(result.receipt);
  $("receiptDialog").showModal();
}

async function openAdmin() {
  const code = $("adminCodeInput").value;
  const result = await api("/api/admin/check", { method: "POST", body: JSON.stringify({ code }) });
  if (!result.ok) {
    $("adminMessage").textContent = "코드가 맞지 않습니다.";
    return;
  }
  sessionStorage.setItem("sdma-admin-code", code);
  location.href = `${base}/admin`;
}

document.addEventListener("DOMContentLoaded", () => {
  $("openLogin").addEventListener("click", showLogin);
  $("loginSubmit").addEventListener("click", login);
  $("employeeInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") login();
  });
  $("alienButton").addEventListener("click", () => {
    alienTapCount += 1;
    if (alienTapCount >= 5) {
      alienTapCount = 0;
      $("adminMessage").textContent = "";
      $("adminDialog").showModal();
      setTimeout(() => $("adminCodeInput").focus(), 50);
    }
  });
  $("adminSubmit").addEventListener("click", openAdmin);
  $("adminCodeInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") openAdmin();
  });
  $("cartToggle").addEventListener("click", () => $("cartDrawer").classList.toggle("hidden"));
  $("closeCart").addEventListener("click", () => $("cartDrawer").classList.add("hidden"));
  $("checkoutButton").addEventListener("click", checkout);
  $("copyReceipt").addEventListener("click", () => navigator.clipboard.writeText($("receiptText").textContent));
  $("continueShopping").addEventListener("click", () => $("receiptDialog").close());
  loadState();
});
