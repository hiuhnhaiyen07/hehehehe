async function activateLocket() {
  const username = document.getElementById("username-input")?.value?.trim();
  const plan = document.getElementById("plan")?.value;

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
      <div style="background:#fff;padding:20px;border-radius:10px;text-align:center;max-width:320px">
        <h3>Quét QR để thanh toán</h3>
        <p><b>MB Bank</b></p>
        <p><b>${data.amount.toLocaleString()}đ</b></p>
        <p>Nội dung: <code>${data.bank.content}</code></p>
        <img src="${qrUrl}" style="width:250px;height:250px"/>
        <br/><br/>
        <button onclick="document.getElementById('qr-popup').remove()">Đóng</button>
      </div>
    </div>
  `);
}
