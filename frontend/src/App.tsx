function App() {
  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="VacancyX home">VacancyX</a>
        <span className="environment">Local workspace</span>
      </header>
      <section className="hero" aria-labelledby="welcome-title">
        <p className="eyebrow">JOB SEARCH WORKSPACE</p>
        <h1 id="welcome-title">Your search, organized.</h1>
        <p className="intro">
          VacancyX will bring job discovery, explainable matching, batch application
          review, and application tracking into one private workspace.
        </p>
        <div className="status" role="status">
          <span className="status-dot" />
          Product foundation initialized
        </div>
      </section>
      <section className="grid" aria-label="Planned workspace modules">
        <article className="panel">
          <h2>Candidate profiles</h2>
          <p>Manage profiles, education, skills, experience, and resume versions.</p>
          <span className="tag">Planned</span>
        </article>
        <article className="panel">
          <h2>Job discovery</h2>
          <p>Configure sources, search criteria, eligibility, and match explanations.</p>
          <span className="tag">Planned</span>
        </article>
        <article className="panel">
          <h2>Application batches</h2>
          <p>Review multiple prepared applications in one session before submission.</p>
          <span className="tag">Planned</span>
        </article>
      </section>
      <footer>Local-first · Candidate-configurable · No mandatory paid services</footer>
    </main>
  );
}

export default App;