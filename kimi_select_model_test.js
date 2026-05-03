// Kimi 模型选择测试 — 在 F12 控制台粘贴运行
// 选择第一个包含"思考"的模型
(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const keyword = "思考";

  // 点击当前模型名称，打开菜单
  document.querySelector(".model-name>.name").click();
  await sleep(500);

  // 找到第一个包含关键字的选项并点击
  const items = document.querySelectorAll(".models-container .model-item");
  for (const item of items) {
    if (item.querySelector(".model-name .name")?.textContent.includes(keyword)) {
      item.click();
      await sleep(500);
      break;
    }
  }

  // 打印最终选中的模型
  console.log(document.querySelector(".model-name>.name").textContent.trim());
})();
