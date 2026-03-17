window.app = (() => {
  const getCookie = (name) => {
    const cookies = document.cookie ? document.cookie.split("; ") : [];
    for (const cookie of cookies) {
      const [key, ...rest] = cookie.split("=");
      if (key === name) return decodeURIComponent(rest.join("="));
    }
    return "";
  };

  const toast = (message, type = "info") => {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const item = document.createElement("div");
    const styleMap = {
      success: "border-emerald-200 bg-emerald-50 text-emerald-700",
      error: "border-rose-200 bg-rose-50 text-rose-700",
      info: "border-sky-200 bg-sky-50 text-sky-700",
    };
    item.className = `pointer-events-auto rounded-2xl border px-4 py-3 text-sm shadow-soft ${styleMap[type] || styleMap.info}`;
    item.textContent = message;
    container.appendChild(item);
    setTimeout(() => item.remove(), 3200);
  };

  const post = async (url, data, button = null) => {
    const body = new URLSearchParams(data);
    const originalText = button?.innerHTML;
    if (button) {
      button.disabled = true;
      button.innerHTML = "处理中...";
    }
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "X-CSRFToken": getCookie("csrftoken"),
          "X-Requested-With": "XMLHttpRequest",
          "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        },
        body,
      });
      const payload = await response.json();
      payload.ok = response.ok && payload.ok !== false;
      if (!response.ok && payload.message) {
        toast(payload.message, "error");
      }
      return payload;
    } catch (error) {
      toast("请求失败，请稍后重试。", "error");
      return null;
    } finally {
      if (button) {
        button.disabled = false;
        button.innerHTML = originalText;
      }
    }
  };

  return { getCookie, toast, post };
})();
