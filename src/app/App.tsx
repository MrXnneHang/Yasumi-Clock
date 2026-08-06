export function App() {
  return (
    <main className="app-shell">
      <section className="scaffold-card" aria-labelledby="app-title">
        <p className="eyebrow">TAURI 2 MIGRATION</p>
        <h1 id="app-title">Yasumi Clock</h1>
        <p className="tagline">用明确的休息提醒，打断停不下来的专注。</p>
        <div className="migration-status" role="status">
          <span className="status-dot" aria-hidden="true" />
          桌面基础工程已就绪
        </div>
        <p className="scope-note">计时核心和完整界面将在后续原子变更中接入。</p>
      </section>
    </main>
  );
}
