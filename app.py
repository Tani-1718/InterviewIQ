"""INTERVIEWIQ landing page and application shell."""

from pathlib import Path
import html

import streamlit as st

from config.roles import ROLES
from config.settings import PROJECT_ROOT, Settings
from database.db import get_latest_user, initialize_database
from modules.dashboard import render_dashboard
from modules.history import render_history_page
from modules.interview_config import (
    render_interview_configuration,
    render_interview_summary,
)
from modules.interview import render_interview_simulator
from modules.onboarding import render_onboarding
from modules.role_selection import render_role_selection
from modules.results import render_results_page
from modules.settings_export import render_settings_export_page


st.set_page_config(
    page_title="INTERVIEWIQ | Your Personal AI Interview Coach",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

settings = Settings.from_env()
initialize_database(settings.database_path)

styles_path = PROJECT_ROOT / "assets" / "styles.css"
st.markdown(
    f"<style>{styles_path.read_text(encoding='utf-8')}</style>",
    unsafe_allow_html=True,
)


def render_landing_page() -> None:
    role_cards_html = "".join(
        f"""
        <article class="role-card">
          <span class="role-card-icon {role['color']}">{role['icon']}</span>
          <span class="role-arrow">↗</span>
          <h3>{html.escape(role['title'])}</h3>
          <p>{html.escape(role['description'])}</p>
          <span class="role-tags">{' · '.join(html.escape(skill) for skill in role['skills'])}</span>
          <span class="role-card-difficulty">Suggested · {html.escape(role['difficulty'])}</span>
        </article>
        """.strip()
        for role in ROLES
    )
    st.markdown(
        f"""
        <header class="topbar">
          <a class="brand" href="#top" aria-label="INTERVIEWIQ home">
            <span class="brand-mark">✦</span><span>interview<span class="brand-iq">iq</span></span>
          </a>
          <nav class="topnav" aria-label="Main navigation">
            <a href="#features">Features</a>
            <a href="#how-it-works">How it works</a>
            <a href="#roles">Roles</a>
            <a href="?page=dashboard" target="_self">Dashboard</a>
            <a href="?page=history" target="_self">History</a>
            <a href="?page=settings" target="_self">Settings &amp; export</a>
          </nav>
          <a class="nav-cta" href="?page=onboarding" target="_self">Get started <span aria-hidden="true">↗</span></a>
        </header>

        <main id="top">
          <section class="hero">
            <div class="hero-copy">
              <div class="eyebrow"><span class="eyebrow-dot"></span> YOUR NEXT INTERVIEW, REIMAGINED</div>
              <h1>Your personal<br />AI interview <span class="gradient-text">coach.</span></h1>
              <p class="hero-subtitle">
                Show up ready. Practice realistic interviews, get thoughtful feedback,
                and build the confidence to take your next big step.
              </p>
              <div class="hero-actions">
                <a class="button-primary" href="?page=onboarding" target="_self">Get started <span aria-hidden="true">→</span></a>
                <a class="button-quiet" href="#features"><span class="play-icon">▶</span> See how it works</a>
              </div>
              <div class="hero-proof">
                <span class="proof-spark">✦</span>
                <span>A practice space centered on you.</span>
              </div>
            </div>
            <div class="hero-visual" aria-label="Interview practice preview">
              <div class="glow-orb"></div>
              <div class="preview-card">
                <div class="preview-top">
                  <div class="preview-brand"><span class="mini-mark">✦</span> Practice session</div>
                  <span class="live-pill"><i></i> PRACTICE PREVIEW</span>
                </div>
                <div class="preview-role">
                  <div class="role-icon">⌘</div>
                  <div><strong>Software Engineer</strong><small>Behavioral · Medium</small></div>
                  <span class="preview-count">01 <span>/ 05</span></span>
                </div>
                <div class="question-label">YOUR QUESTION</div>
                <div class="preview-question">Tell me about a time you had to debug a challenging issue. How did you approach it?</div>
                <div class="preview-divider"></div>
                <div class="answer-label"><span>Your answer</span><span>Text practice</span></div>
                <div class="answer-lines"><i></i><i></i><i></i></div>
                <div class="preview-footer"><span>Take your time. You’ve got this.</span><span class="send-icon">↑</span></div>
              </div>
              <div class="floating-note"><span class="note-icon">✧</span><span><b>Thoughtful feedback</b><small>Made for your answer</small></span></div>
              <div class="floating-score"><span class="score-ring">↗</span><span><b>Growing with every</b><small>practice session</small></span></div>
            </div>
          </section>

          <section class="trust-strip">
            <span>PREPARE WITH PURPOSE</span>
            <i></i><span>Practice at your pace</span>
            <i></i><span>Feedback that feels human</span>
            <i></i><span>Progress you can see</span>
          </section>

          <section class="section-block" id="features">
            <div class="section-heading">
              <div class="eyebrow">A BETTER WAY TO PREPARE</div>
              <h2>Less guessing.<br /><span class="muted-heading">More growing.</span></h2>
              <p>Interview prep should help you feel capable, not overwhelmed. Make every practice count.</p>
            </div>
            <div class="feature-grid">
              <article class="feature-card feature-card-large">
                <div class="feature-icon purple-icon">✧</div>
                <div class="feature-kicker">PRACTICE THAT ADAPTS</div>
                <h3>Questions with a point of view.</h3>
                <p>Get role-focused prompts that respond to what you say, so every conversation feels relevant to your goals.</p>
                <div class="question-chips"><span>Role-specific</span><span>Natural follow-ups</span><span>At your level</span></div>
                <div class="card-decoration">✳</div>
              </article>
              <article class="feature-card">
                <div class="feature-icon blue-icon">⌁</div>
                <div class="feature-kicker">FEEDBACK THAT HELPS</div>
                <h3>Know what to keep—and what to try next.</h3>
                <p>Understand where your answer landed and leave with a clear, practical next step.</p>
              </article>
              <article class="feature-card">
                <div class="feature-icon cyan-icon">◷</div>
                <div class="feature-kicker">PROGRESS THAT MATTERS</div>
                <h3>Build confidence one session at a time.</h3>
                <p>Reflect on how you feel before and after each practice and see your preparation take shape.</p>
              </article>
            </div>
          </section>

          <section class="workflow-section" id="how-it-works">
            <div class="workflow-heading">
              <div class="eyebrow">SIMPLE BY DESIGN</div>
              <h2>From “what if?” to<br /><span class="gradient-text">“I’m ready.”</span></h2>
              <p>A supportive practice loop that puts you—not the pressure—at the center.</p>
            </div>
            <div class="workflow-track">
              <article class="workflow-step"><span class="step-number">01</span><div class="step-icon">◎</div><h3>Choose your role</h3><p>Tell us what you’re working toward.</p></article>
              <div class="step-connector"></div>
              <article class="workflow-step"><span class="step-number">02</span><div class="step-icon">✳</div><h3>Get a question</h3><p>Take on a realistic, relevant prompt.</p></article>
              <div class="step-connector"></div>
              <article class="workflow-step"><span class="step-number">03</span><div class="step-icon">↗</div><h3>Share your answer</h3><p>Think it through and answer your way.</p></article>
              <div class="step-connector"></div>
              <article class="workflow-step"><span class="step-number">04</span><div class="step-icon">◇</div><h3>Get thoughtful feedback</h3><p>See strengths and ways to improve.</p></article>
              <div class="step-connector"></div>
              <article class="workflow-step"><span class="step-number">05</span><div class="step-icon">⟳</div><h3>Keep getting ready</h3><p>Carry your learning into the next round.</p></article>
            </div>
            <div class="workflow-cta">
              <span>Small steps make a big difference.</span>
              <a class="button-primary button-small" href="#roles">Find your practice path <span aria-hidden="true">→</span></a>
            </div>
          </section>

          <section class="roles-section" id="roles">
            <div class="roles-intro">
              <div class="eyebrow">YOUR GOAL, YOUR PRACTICE</div>
              <h2>Made for the work<br />you want to do.</h2>
              <p>Choose a direction. We’ll help you get comfortable with the conversations that come with it.</p>
              <a class="text-link" href="#how-it-works">See how it works <span aria-hidden="true">→</span></a>
            </div>
            <div class="roles-grid">
              {role_cards_html}
            </div>
          </section>

          <section class="closing-banner">
            <div class="closing-spark">✦</div>
            <div><div class="eyebrow">YOU DON’T HAVE TO FIGURE IT OUT ALONE</div><h2>Your next interview can feel different.</h2><p>Start with one practice question. See where it takes you.</p></div>
            <a class="button-primary" href="?page=onboarding" target="_self">Let’s get started <span aria-hidden="true">→</span></a>
          </section>
          <footer class="footer"><a class="brand" href="#top"><span class="brand-mark">✦</span><span>interview<span class="brand-iq">iq</span></span></a><span>Practice with purpose. Show up as yourself.</span><span>© 2026 INTERVIEWIQ</span></footer>
        </main>
        """,
        unsafe_allow_html=True,
    )


page = st.query_params.get("page", "landing")
profile = get_latest_user(db_path=settings.database_path)

if page == "onboarding":
    render_onboarding(profile, settings.database_path)
elif page == "dashboard":
    render_dashboard(profile, settings.database_path)
elif page == "roles":
    render_role_selection(profile, settings.database_path)
elif page == "configure":
    render_interview_configuration(profile)
elif page == "summary":
    render_interview_summary(profile, settings.database_path)
elif page == "interview":
    render_interview_simulator(profile, settings)
elif page == "results":
    render_results_page(settings, profile)
elif page == "history":
    render_history_page(profile, settings.database_path)
elif page == "settings":
    render_settings_export_page(profile, settings)
else:
    render_landing_page()
