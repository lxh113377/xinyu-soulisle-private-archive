/* 心屿 · 滚动叙事控制器
 * 有 GSAP+ScrollTrigger：滚动进度 → 镜头/文案动画；无则降级原生 scroll 监听。
 * ⚠️ 每幕只能有「一条」时间轴独占 .act-copy 的 y/opacity：
 *    旧实现用「进入 fromTo + 淡出 to(scrub)」两条补间争抢同一属性，
 *    淡出补间会把首次渲染时的值（尚未进入时的 opacity:0）记为起点，
 *    回滚到 progress 0 时恢复的就是这个错误起点 → 滚到底再往上滚，文案消失回不来。
 */
window.ScrollStory = (function () {
  function init(onProgress, onAct) {
    const story = document.getElementById("story");
    const acts = [...document.querySelectorAll(".act")];

    if (window.gsap && window.ScrollTrigger) {
      gsap.registerPlugin(ScrollTrigger);
      // 字体/布局后到齐会改变幕高，load 后刷新一次触发器量程，避免淡入区间错位
      addEventListener("load", () => { if (window.ScrollTrigger) window.ScrollTrigger.refresh(); });
      gsap.to({}, {
        scrollTrigger: {
          trigger: story, start: "top top", end: "bottom bottom", scrub: true,
          onUpdate: (self) => onProgress(self.progress)
        }
      });
      acts.forEach((a, i) => {
        const copy = a.querySelector(".act-copy");
        // 一条 scrub 时间轴覆盖「淡入 → 满显 → 淡出」，天然双向可逆。
        // ⚠️ trigger 必须是「面板自身」而不是幕（section）：幕高 = 视口高，面板只占幕中央一小块，
        //    拿幕当 trigger 时淡入淡出全部落在面板还看不见的空白区 ——
        //    实测（旧版）：面板可见期间 opacity 恒在 0.93~1.00，肉眼完全看不出变化。
        //    换成面板自身后，区间正好等于「面板从下缘进屏 → 从上缘离屏」，淡入淡出全程可见。
        const tl = gsap.timeline({
          defaults: { ease: "none" },
          scrollTrigger: { trigger: copy, start: "top bottom", end: "bottom top", scrub: 0.6 }
        });
        // 节奏（第二版 · 强化）：半透明是可见期的「常态」，只有逼近屏幕正中才短暂变实。
        // 旧版（0.85→1 / 停 0.25 / 1→0）实测可见区间 opacity=1.00 连占 6 档、明显更透明只占 23%
        // 且都发生在面板快滑出屏幕时 → 观感上「一直很实，看不出随滚动变化」。
        const DIM_OP = 0.3;   // 常态半透明度：让后面的星雾透出来
        tl.fromTo(copy, { y: 60, opacity: 0 }, { y: 0, opacity: DIM_OP, duration: 0.45, ease: "power2.out" })
          .to(copy, { opacity: 1, duration: 0.5, ease: "power2.inOut" })
          .to(copy, { opacity: 1, duration: 0.2 })
          .to(copy, { opacity: DIM_OP, duration: 0.5, ease: "power2.inOut" })
          .to(copy, { y: -28, opacity: 0, duration: 0.55, ease: "power1.in" });

        const io = new IntersectionObserver((es) => {
          es.forEach(e => { if (e.isIntersecting) onAct(i + 1); });
        }, { threshold: 0.5 });
        io.observe(a);
      });
    } else {
      addEventListener("scroll", () => {
        const max = document.documentElement.scrollHeight - innerHeight;
        onProgress(max > 0 ? scrollY / max : 0);
      }, { passive: true });
      const io = new IntersectionObserver((es) => {
        es.forEach(e => { if (e.isIntersecting) onAct(+e.target.dataset.act); });
      }, { threshold: 0.5 });
      acts.forEach(a => io.observe(a));
    }
  }
  return { init };
})();
