import os
import json
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import plotly.express as px
from groq import Groq
from dotenv import load_dotenv
from fpdf import FPDF

# ---------- Setup ----------
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

st.set_page_config(page_title="AI Project Planner", layout="wide")

# Dark-leaning styling
st.markdown(
    """
    <style>
    .main { background-color: #020617; color: #e5e7eb; }
    .stButton>button {
        background-color: #1d4ed8;
        color: white;
        border-radius: 6px;
        border: none;
        padding: 0.4rem 0.8rem;
    }
    .stDownloadButton>button {
        background-color: #0f766e;
        color: white;
        border-radius: 6px;
        border: none;
        padding: 0.4rem 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "saved_plans" not in st.session_state:
    st.session_state.saved_plans = {}
if "current_plan" not in st.session_state:
    st.session_state.current_plan = None
if "current_plan_name" not in st.session_state:
    st.session_state.current_plan_name = "My Project Plan"


# ---------- Helper: call Groq and get structured JSON ----------
def generate_structured_plan(description: str, temperature: float, max_tokens: int):
    system_prompt = (
        "You are an expert project planner. "
        "Return ONLY valid JSON (no markdown, no commentary). "
        "Use this structure:\n"
        "{\n"
        '  "overview": "short paragraph",\n'
        '  "objectives": ["obj1", "obj2"],\n'
        '  "tasks": [\n'
        '    {"name": "Task name", "owner": "Role or person", "start_day": 1, "duration_days": 3, "status": "Planned"}\n'
        "  ],\n"
        '  "risks": [\n'
        '    {"risk": "Risk description", "impact": "Low/Medium/High", "likelihood": "Low/Medium/High", "mitigation": "Mitigation plan"}\n'
        "  ],\n"
        '  "tools": ["Tool 1", "Tool 2"],\n'
        '  "next_steps": ["Step 1", "Step 2"]\n'
        "}\n"
        "Days are relative (start_day 1 = project start)."
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": description},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )

    raw = response.choices[0].message.content
    return json.loads(raw)


# ---------- Helper: build Gantt dataframe ----------
def build_gantt_df(tasks):
    start_date = datetime.today().date()
    rows = []
    for t in tasks:
        s = start_date + timedelta(days=int(t.get("start_day", 1)) - 1)
        d = int(t.get("duration_days", 1))
        e = s + timedelta(days=d)
        rows.append(
            {
                "Task": t.get("name", "Task"),
                "Owner": t.get("owner", "Unassigned"),
                "Start": s,
                "Finish": e,
                "Status": t.get("status", "Planned"),
            }
        )
    return pd.DataFrame(rows)


# ---------- Helper: export PDF ----------
def generate_pdf(plan: dict) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "AI Project Plan", ln=True)

    pdf.set_font("Arial", "", 12)

    def add_section(title, content):
        pdf.ln(5)
        pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 8, title, ln=True)
        pdf.set_font("Arial", "", 11)
        if isinstance(content, str):
            pdf.multi_cell(0, 6, content)
        elif isinstance(content, list):
            for item in content:
                pdf.multi_cell(0, 6, f"- {item}")
        pdf.ln(2)

    add_section("Overview", plan.get("overview", ""))
    add_section("Objectives", plan.get("objectives", []))

    tasks = plan.get("tasks", [])
    task_lines = [
        f"{t.get('name','Task')} (Owner: {t.get('owner','N/A')}, "
        f"Start Day: {t.get('start_day',1)}, Duration: {t.get('duration_days',1)} days)"
        for t in tasks
    ]
    add_section("Tasks", task_lines)

    risks = plan.get("risks", [])
    risk_lines = [
        f"{r.get('risk','Risk')} "
        f"[Impact: {r.get('impact','')}, Likelihood: {r.get('likelihood','')}] "
        f"Mitigation: {r.get('mitigation','')}"
        for r in risks
    ]
    add_section("Risks", risk_lines)

    add_section("Tools & Tech Stack", plan.get("tools", []))
    add_section("Next Steps", plan.get("next_steps", []))

    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    return pdf_bytes


# ---------- Sidebar navigation ----------
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Planner", "Saved Plans"],
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Theme:** Dark-leaning via custom CSS. "
    "You can also enable full dark mode in Streamlit settings."
)


# ---------- PAGE: Planner ----------
if page == "Planner":
    st.title("📘 AI Project Planner (Groq – Llama 3.3 70B)")

    st.subheader("📝 Project Description")
    description = st.text_area("Describe your project or idea:", height=150)

    col1, col2, col3 = st.columns(3)
    with col1:
        temperature = st.slider("Creativity", 0.0, 1.0, 0.4)
    with col2:
        max_tokens = st.slider("Max Tokens", 300, 2500, 1200)
    with col3:
        plan_name = st.text_input(
            "Plan Name (for saving)",
            value=st.session_state.current_plan_name,
        )

    generate = st.button("🚀 Generate Project Plan")

    if generate:
        if not api_key:
            st.error("Missing GROQ_API_KEY in your .env file.")
        elif not description.strip():
            st.error("Please enter a project description.")
        else:
            with st.spinner("Generating your structured project plan..."):
                try:
                    plan = generate_structured_plan(description, temperature, max_tokens)

                    st.session_state.current_plan = plan
                    st.session_state.current_plan_name = plan_name

                    st.success("Project Plan Generated!")

                    tabs = st.tabs(
                        [
                            "Overview",
                            "Objectives",
                            "Tasks",
                            "Timeline",
                            "Risks",
                            "Tools",
                            "Next Steps",
                            "Export",
                        ]
                    )

                    # --- Overview tab ---
                    with tabs[0]:
                        with st.expander("Project Overview", expanded=True):
                            st.write(plan.get("overview", ""))

                    # --- Objectives tab ---
                    with tabs[1]:
                        with st.expander("Objectives", expanded=True):
                            st.write(plan.get("objectives", []))

                    # --- Tasks tab ---
                    tasks = plan.get("tasks", [])
                    with tabs[2]:
                        with st.expander("Task Breakdown", expanded=True):
                            if tasks:
                                st.dataframe(pd.DataFrame(tasks), use_container_width=True)
                            else:
                                st.info("No tasks returned by the model.")

                    # --- Timeline tab (optimized) ---
                    with tabs[3]:
                        with st.expander("Timeline (Gantt Chart)", expanded=True):
                            if tasks:
                                gantt_df = build_gantt_df(tasks)
                                gantt_df["TaskShort"] = gantt_df["Task"].apply(
                                    lambda x: x if len(x) <= 30 else x[:27] + "..."
                                )

                                fig = px.timeline(
                                    gantt_df,
                                    x_start="Start",
                                    x_end="Finish",
                                    y="TaskShort",
                                    color="Owner",
                                    hover_data=["Task", "Owner", "Status", "Start", "Finish"],
                                )

                                fig.update_yaxes(autorange="reversed")

                                fig.update_layout(
                                    height=600,
                                    margin=dict(l=10, r=10, t=40, b=40),
                                    xaxis_title="",
                                    yaxis_title="",
                                    bargap=0.3,
                                    hoverlabel=dict(
                                        bgcolor="#1f2937",
                                        font_size=12,
                                        font_color="white",
                                    ),
                                    legend=dict(
                                        orientation="h",
                                        yanchor="bottom",
                                        y=1.02,
                                        xanchor="right",
                                        x=1,
                                    ),
                                )

                                st.write(
                                    "<div style='overflow-x: auto; padding-bottom: 10px;'>",
                                    unsafe_allow_html=True,
                                )
                                st.plotly_chart(fig, use_container_width=True)
                                st.write("</div>", unsafe_allow_html=True)
                            else:
                                st.info("Not enough task data to build a timeline.")

                    # --- Risks tab ---
                    risks = plan.get("risks", [])
                    with tabs[4]:
                        with st.expander("Risk Matrix", expanded=True):
                            if risks:
                                st.dataframe(pd.DataFrame(risks), use_container_width=True)
                            else:
                                st.info("No risks returned by the model.")

                    # --- Tools tab ---
                    with tabs[5]:
                        with st.expander("Tools & Tech Stack", expanded=True):
                            st.write(plan.get("tools", []))

                    # --- Next Steps tab ---
                    with tabs[6]:
                        with st.expander("Next Steps", expanded=True):
                            st.write(plan.get("next_steps", []))

                    # --- Export tab (fixed layout) ---
                    with tabs[7]:
                        st.markdown("### Export & Save")

                        col_a, col_b = st.columns([1, 1])

                        with col_a:
                            if st.button("💾 Save Plan"):
                                st.session_state.saved_plans[plan_name] = plan
                                st.success(f"Plan '{plan_name}' saved.")

                        with col_b:
                            if st.session_state.current_plan:
                                pdf_bytes = generate_pdf(st.session_state.current_plan)
                                st.download_button(
                                    "📥 Download PDF",
                                    data=pdf_bytes,
                                    file_name=f"{plan_name.replace(' ', '_')}.pdf",
                                    mime="application/pdf",
                                )

                        # JSON export gets its own row
                        if st.session_state.current_plan:
                            json_bytes = json.dumps(
                                st.session_state.current_plan,
                                indent=2,
                            ).encode("utf-8")
                            st.download_button(
                                "📥 Download JSON",
                                data=json_bytes,
                                file_name=f"{plan_name.replace(' ', '_')}.json",
                                mime="application/json",
                            )

                except json.JSONDecodeError:
                    st.error("Model returned invalid JSON. Try again with lower creativity.")
                except Exception as e:
                    st.error(f"Error: {e}")


# ---------- PAGE: Saved Plans ----------
elif page == "Saved Plans":
    st.title("📂 Saved Project Plans")

    if not st.session_state.saved_plans:
        st.info("No saved plans yet. Generate and save one from the Planner page.")
    else:
        names = list(st.session_state.saved_plans.keys())
        selected = st.selectbox("Select a saved plan:", names)

        if selected:
            plan = st.session_state.saved_plans[selected]

            tabs = st.tabs(
                [
                    "Overview",
                    "Objectives",
                    "Tasks",
                    "Timeline",
                    "Risks",
                    "Tools",
                    "Next Steps",
                    "Export",
                ]
            )

            # --- Overview tab ---
            with tabs[0]:
                with st.expander(f"Overview – {selected}", expanded=True):
                    st.write(plan.get("overview", ""))

            # --- Objectives tab ---
            with tabs[1]:
                with st.expander("Objectives", expanded=True):
                    st.write(plan.get("objectives", []))

            # --- Tasks tab ---
            tasks = plan.get("tasks", [])
            with tabs[2]:
                with st.expander("Task Breakdown", expanded=True):
                    if tasks:
                        st.dataframe(pd.DataFrame(tasks), use_container_width=True)
                    else:
                        st.info("No tasks in this plan.")

            # --- Timeline tab (optimized) ---
            with tabs[3]:
                with st.expander("Timeline (Gantt Chart)", expanded=True):
                    if tasks:
                        gantt_df = build_gantt_df(tasks)
                        gantt_df["TaskShort"] = gantt_df["Task"].apply(
                            lambda x: x if len(x) <= 30 else x[:27] + "..."
                        )

                        fig = px.timeline(
                            gantt_df,
                            x_start="Start",
                            x_end="Finish",
                            y="TaskShort",
                            color="Owner",
                            hover_data=["Task", "Owner", "Status", "Start", "Finish"],
                        )

                        fig.update_yaxes(autorange="reversed")

                        fig.update_layout(
                            height=600,
                            margin=dict(l=10, r=10, t=40, b=40),
                            xaxis_title="",
                            yaxis_title="",
                            bargap=0.3,
                            hoverlabel=dict(
                                bgcolor="#1f2937",
                                font_size=12,
                                font_color="white",
                            ),
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=1.02,
                                xanchor="right",
                                x=1,
                            ),
                        )

                        st.write(
                            "<div style='overflow-x: auto; padding-bottom: 10px;'>",
                            unsafe_allow_html=True,
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        st.write("</div>", unsafe_allow_html=True)
                    else:
                        st.info("Not enough task data to build a timeline.")

            # --- Risks tab ---
            risks = plan.get("risks", [])
            with tabs[4]:
                with st.expander("Risk Matrix", expanded=True):
                    if risks:
                        st.dataframe(pd.DataFrame(risks), use_container_width=True)
                    else:
                        st.info("No risks in this plan.")

            # --- Tools tab ---
            with tabs[5]:
                with st.expander("Tools & Tech Stack", expanded=True):
                    st.write(plan.get("tools", []))

            # --- Next Steps tab ---
            with tabs[6]:
                with st.expander("Next Steps", expanded=True):
                    st.write(plan.get("next_steps", []))

            # --- Export tab (fixed layout) ---
            with tabs[7]:
                st.markdown("### Export & Import")

                col1, col2 = st.columns([1, 1])

                with col1:
                    pdf_bytes = generate_pdf(plan)
                    st.download_button(
                        "📥 Download PDF",
                        data=pdf_bytes,
                        file_name=f"{selected.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                    )

                with col2:
                    json_bytes = json.dumps(plan, indent=2).encode("utf-8")
                    st.download_button(
                        "📥 Download JSON",
                        data=json_bytes,
                        file_name=f"{selected.replace(' ', '_')}.json",
                        mime="application/json",
                    )

                st.markdown("### 📤 Import Plan from JSON")
                uploaded = st.file_uploader("Upload a plan JSON file", type=["json"])
                if uploaded is not None:
                    try:
                        data = json.load(uploaded)
                        name = st.text_input("Name for imported plan", value="Imported Plan")
                        if st.button("Save Imported Plan"):
                            st.session_state.saved_plans[name] = data
                            st.success(f"Imported plan saved as '{name}'.")
                    except Exception as e:
                        st.error(f"Failed to import JSON: {e}")
