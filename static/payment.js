// static/payment.js

async function activateLocket() {
  const username = document.getElementById("username-input")?.value?.trim();
  const planEl = document.querySelector(".plan-card.selected");

  if (!username || !planEl) {
    alert("Nhập username và chọn gói");
    return;
  }

  const onclick = planEl.getAttribute("onclick");
  const plan = onclick.match(/'(.+?)'/)?.[1];

  if (!plan) {
    alert("Không xác định được gói");
    return;
  }

  const res = await fetch("/api/create-order", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, plan })
  });

  const data = await res.json();

  if (!data.success) {
    alert("Tạo đơn thất bại");
    return;
  }

  const qrData = `MB|${data.bank.account_number}|${data.amount}|${data.bank.content}`;
  const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(qrData)}`;

  document.body.insertAdjacentHTML("beforeend", `
    <div id="qr-popup" style="
      position:fixed; inset:0; background:rgba(0,0,0,.6);
      display:flex; align-items:center; justify-content:center; z-index:9999">
      <div style="background:#fff;padding:20px;border-radius:10px;text-align:center">
        <h3>Quét QR để thanh toán</h3>
        <p><b>MB Bank</b></p>
        <p><b>${data.amount.toLocaleString()}đ</b></p>
        <p>Nội dung: <code>${data.bank.content}</code></p>
        <img src="${qrUrl}" />
        <br/><br/>
        <button onclick="document.getElementById('qr-popup').remove()">Đóng</button>
      </div>
    </div>
  `);
}
