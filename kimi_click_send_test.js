// Kimi 点击发送按钮测试 — 在 F12 控制台粘贴运行
(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // 点击发送按钮
  document.querySelector(".send-button-container").click();
  await sleep(500);

  // 打印当前页面地址
  console.log(window.location.href);
})();
