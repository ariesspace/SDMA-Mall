const base = document.body.dataset.basePath;
const $ = (id) => document.getElementById(id);
const money = (value) => `${Number(value || 0).toLocaleString()}점`;
let state = { users: [], products: [], receipts: { text: "", list: [] } };

function adminCode() {
  return $("adminCode").value || sessionStorage.getItem("sdma-admin-code") || "";
}

async function api(path, body = {}) {
  const response = await fetch(base + path, {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8", "X-Admin-Code": adminCode() },
    body: JSON.stringify(body),
  });
  return response.json();
}

async function loadAdmin() {
  const code = adminCode();
  if (code) $("adminCode").value = code;
  const result = await api("/api/admin/state");
  if (!result.ok) {
    $("receiptSummary").textContent = result.message || "관리자 코드를 입력해주세요.";
    return;
  }
  state = result.state;
  render();
}

function render() {
  $("usersBody").innerHTML = state.users.map((user) => `
    <tr>
      <td>${user.employee_no}</td>
      <td>${user.name || "-"}</td>
      <td>${user.team || "-"}</td>
      <td><b>${money(user.points)}</b></td>
      <td><button class="pixel-button" type="button" onclick="editUser(${user.id})">수정</button></td>
    </tr>
  `).join("") || `<tr><td colspan="5">등록된 사용자가 없습니다.</td></tr>`;

  $("adminProducts").innerHTML = state.products.map((product) => `
    <div class="admin-product">
      <strong>${product.name}</strong>
      <p>${money(product.price)} / 재고 ${product.stock === null ? "제한 없음" : product.stock} / ${product.is_active ? "판매 중" : "숨김"}</p>
      <button class="pixel-button" type="button" onclick="editProduct(${product.id})">수정</button>
    </div>
  `).join("") || `<p>등록된 상품이 없습니다.</p>`;

  $("receiptSummary").textContent = state.receipts.text || "아직 구매 내역이 없습니다.";
  $("receiptCards").innerHTML = state.receipts.list.map((receipt) => {
    const order = receipt.order;
    const items = receipt.items.map((item) => `<li>${item.product_name} ${item.quantity}개 (${money(item.unit_price * item.quantity)})</li>`).join("");
    return `
      <div class="receipt-card">
        <strong>${order.created_at} / ${order.employee_no} ${order.name || ""}</strong>
        <ul>${items}</ul>
        <b>총 ${money(order.total_points)}</b>
      </div>
    `;
  }).join("");
}

function editUser(id) {
  const user = state.users.find((item) => item.id === id);
  if (!user) return;
  $("userEmployeeNo").value = user.employee_no;
  $("userName").value = user.name;
  $("userTeam").value = user.team;
  $("userPoints").value = user.points;
  $("userEmployeeNo").focus();
}

function editProduct(id) {
  const product = state.products.find((item) => item.id === id);
  if (!product) return;
  $("productId").value = product.id;
  $("productName").value = product.name;
  $("productPrice").value = product.price;
  $("productOriginalPrice").value = product.original_price;
  $("productStock").value = product.stock ?? "";
  $("productImage").value = product.image_url;
  $("productDescription").value = product.description;
  $("productActive").checked = Boolean(product.is_active);
  $("productName").focus();
}

async function saveUser() {
  const result = await api("/api/admin/users", {
    employee_no: $("userEmployeeNo").value,
    name: $("userName").value,
    team: $("userTeam").value,
    points: $("userPoints").value,
  });
  $("userMessage").textContent = result.message || "";
  if (result.ok) {
    state = result.state;
    render();
  }
}

async function saveProduct() {
  const result = await api("/api/admin/products", {
    id: $("productId").value,
    name: $("productName").value,
    price: $("productPrice").value,
    original_price: $("productOriginalPrice").value,
    stock: $("productStock").value,
    image_url: $("productImage").value,
    description: $("productDescription").value,
    is_active: $("productActive").checked,
  });
  $("productMessage").textContent = result.message || "";
  if (result.ok) {
    state = result.state;
    render();
    $("productId").value = "";
  }
}

async function resetOrders() {
  if (!confirm("구매 내역만 초기화할까요? 사용자 점수와 상품은 유지됩니다.")) return;
  const result = await api("/api/admin/reset-orders");
  if (result.ok) {
    state = result.state;
    render();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  $("saveUser").addEventListener("click", saveUser);
  $("saveProduct").addEventListener("click", saveProduct);
  $("resetOrders").addEventListener("click", resetOrders);
  $("copyAllReceipts").addEventListener("click", () => navigator.clipboard.writeText($("receiptSummary").textContent));
  $("adminCode").addEventListener("change", loadAdmin);
  loadAdmin();
});
