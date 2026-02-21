// static/payment.js
console.log("payment.js loaded");

async function createOrder() {
  console.log("createOrder called");

  const username = document.getElementById("username").value.trim();
  const plan = document.getElementById("plan").value;

  if (!username || !plan) {
    alert("Vui lòng nhập username và chọn gói");
    return;
  }

  const res = await fetch("/api/create-order", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, plan })
  });

  const data = await res.json();
  console.log("API response:", data);

  if (!data.success) {
    alert("Tạo đơn thất bại");
    return;
  }

  const qrUrl = `https://img.vietqr.io/image/MB-${data.bank.account_number}-compact.png?amount=${data.amount}&addInfo=${encodeURIComponent(data.bank.content)}&accountName=${encodeURIComponent(data.bank.account_name)}`;

  document.body.insertAdjacentHTML("beforeend", `
    <div style="
      position:fixed; inset:0;
      background:rgba(0,0,0,0.6);
      display:flex; align-items:center; justify-content:center;
      z-index:9999;
    ">
      <div style="background:#fff;padding:20px;border-radius:12px;text-align:center">
        <h3>Quét QR để thanh toán</h3>
        <img src="${qrUrl}" width="250">
        <p><b>${data.amount.toLocaleString()}đ</b></p>
        <p>${data.bank.content}</p>
        <button onclick="this.parentElement.parentElement.remove()">Đóng</button>
      </div>
    </div>
  `);
}
