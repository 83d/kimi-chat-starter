/*
 * Kimi contenteditable 输入框注入测试脚本
 * 用法：F12 控制台粘贴整段代码，然后依次运行：
 *   await KimiInputTest.case1('你好，这是 case1')
 *   await KimiInputTest.case2('你好，这是 case2')
 *   ...
 *   await KimiInputTest.runAll('统一测试文本')
 */
(() => {
  const EDITOR_SELECTOR = '.chat-input-editor[contenteditable="true"], [data-lexical-editor="true"][contenteditable="true"], div[role="textbox"][contenteditable="true"]';

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  function getEditor() {
    const editor = document.querySelector(EDITOR_SELECTOR);
    if (!editor) {
      throw new Error(`未找到输入框，选择器：${EDITOR_SELECTOR}`);
    }
    return editor;
  }

  function focusEditor(editor = getEditor()) {
    editor.scrollIntoView({ block: 'center', inline: 'nearest' });
    editor.focus();
    const range = document.createRange();
    range.selectNodeContents(editor);
    range.collapse(false);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    return editor;
  }

  function dispatchInputEvents(editor, inputType = 'insertText', data = null) {
    editor.dispatchEvent(new InputEvent('beforeinput', {
      bubbles: true,
      cancelable: true,
      inputType,
      data,
    }));
    editor.dispatchEvent(new InputEvent('input', {
      bubbles: true,
      cancelable: false,
      inputType,
      data,
    }));
    editor.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function setNativeTextContent(editor, text) {
    editor.textContent = '';
    const p = document.createElement('p');
    p.textContent = text;
    editor.appendChild(p);
  }

  function report(name, text) {
    const editor = getEditor();
    console.log(`[${name}] 已执行，当前 DOM 文本：`, editor.innerText || editor.textContent);
    console.log('如果页面输入框显示了文本，并且发送按钮状态变为可点，则该方法大概率有效。测试文本：', text);
  }

  async function case1(text = 'case1: execCommand insertText') {
    const editor = focusEditor();
    document.execCommand('selectAll', false, null);
    document.execCommand('insertText', false, text);
    dispatchInputEvents(editor, 'insertText', text);
    report('case1', text);
  }

  async function case2(text = 'case2: range + text node + input event') {
    const editor = focusEditor();
    editor.innerHTML = '<p><br></p>';
    focusEditor(editor);
    const selection = window.getSelection();
    const range = selection.getRangeAt(0);
    range.deleteContents();
    range.insertNode(document.createTextNode(text));
    range.collapse(false);
    dispatchInputEvents(editor, 'insertText', text);
    report('case2', text);
  }

  async function case3(text = 'case3: innerHTML paragraph + input event') {
    const editor = focusEditor();
    editor.innerHTML = `<p>${escapeHtml(text)}</p>`;
    focusEditor(editor);
    dispatchInputEvents(editor, 'insertText', text);
    report('case3', text);
  }

  async function case4(text = 'case4: textContent paragraph + input event') {
    const editor = focusEditor();
    setNativeTextContent(editor, text);
    focusEditor(editor);
    dispatchInputEvents(editor, 'insertText', text);
    report('case4', text);
  }

  async function case5(text = 'case5: clipboard paste event') {
    const editor = focusEditor();
    document.execCommand('selectAll', false, null);
    const data = new DataTransfer();
    data.setData('text/plain', text);
    const pasteEvent = new ClipboardEvent('paste', {
      bubbles: true,
      cancelable: true,
      clipboardData: data,
    });
    editor.dispatchEvent(pasteEvent);
    await sleep(50);
    if (!(editor.innerText || editor.textContent || '').includes(text)) {
      document.execCommand('insertText', false, text);
    }
    dispatchInputEvents(editor, 'insertFromPaste', text);
    report('case5', text);
  }

  async function case6(text = 'case6: keyboard events + execCommand') {
    const editor = focusEditor();
    document.execCommand('selectAll', false, null);
    for (const char of text) {
      editor.dispatchEvent(new KeyboardEvent('keydown', { key: char, bubbles: true, cancelable: true }));
      document.execCommand('insertText', false, char);
      editor.dispatchEvent(new KeyboardEvent('keyup', { key: char, bubbles: true, cancelable: true }));
      dispatchInputEvents(editor, 'insertText', char);
      await sleep(5);
    }
    report('case6', text);
  }

  async function case7(text = 'case7: React/Vue friendly composition events') {
    const editor = focusEditor();
    document.execCommand('selectAll', false, null);
    editor.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true, data: '' }));
    editor.dispatchEvent(new CompositionEvent('compositionupdate', { bubbles: true, data: text }));
    document.execCommand('insertText', false, text);
    editor.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true, data: text }));
    dispatchInputEvents(editor, 'insertCompositionText', text);
    report('case7', text);
  }

  async function case8(text = 'case8: 直接给 p 写文本 + 冒泡事件') {
    const editor = focusEditor();
    let p = editor.querySelector('p');
    if (!p) {
      p = document.createElement('p');
      editor.appendChild(p);
    }
    p.textContent = text;
    focusEditor(editor);
    ['keydown', 'beforeinput', 'input', 'keyup', 'change'].forEach((type) => {
      const event = type.includes('input')
        ? new InputEvent(type, { bubbles: true, inputType: 'insertText', data: text })
        : new Event(type, { bubbles: true });
      editor.dispatchEvent(event);
    });
    report('case8', text);
  }

  // 推荐正式使用这个方法：目前测试结果最干净、最接近真实中文输入。
  async function inputKimiText(text = '你好 Kimi，这是最佳方法测试') {
    return case7(text);
  }

  async function runBest(text = '你好 Kimi，这是最佳方法测试') {
    await inputKimiText(text);
    console.log('推荐方法已执行。请观察输入框文本和发送按钮状态。');
  }

  async function runAll(baseText = 'Kimi 输入框自动填充测试') {
    for (const [index, fn] of [case1, case2, case3, case4, case5, case6, case7, case8].entries()) {
      console.group(`运行 case${index + 1}`);
      await fn(`${baseText} - case${index + 1} - ${new Date().toLocaleTimeString()}`);
      console.groupEnd();
      await sleep(800);
    }
    console.log('全部 case 已运行完。当前推荐正式使用 case7 / inputKimiText。');
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  window.inputKimiText = inputKimiText;
  window.KimiInputTest = {
    getEditor,
    focusEditor,
    inputKimiText,
    runBest,
    case1,
    case2,
    case3,
    case4,
    case5,
    case6,
    case7,
    case8,
    runAll,
  };

  console.log('KimiInputTest 已加载。推荐测试：await inputKimiText("你好 Kimi，这是最佳方法测试")');
  console.log('也可以运行：await KimiInputTest.runBest("你好 Kimi")');
})();
