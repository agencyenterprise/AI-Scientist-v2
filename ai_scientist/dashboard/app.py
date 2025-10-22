import sys
import time
from functools import partial
from pathlib import Path
from typing import Dict, Iterable, Optional

import streamlit as st

# Ensure project root on path for imports
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_scientist.dashboard import utils
from ai_scientist.dashboard.runpod_utils import deploy_to_runpod
from ai_scientist.dashboard.view_models import (
    LOG_ROOT,
    ExperimentSnapshot,
    IdeaDocument,
    load_all_ideas,
    load_experiment_snapshots,
    read_log_tail,
)
from ai_scientist.llm import create_client, get_response_from_llm


AUTO_REFRESH_SECONDS = 5
DEFAULT_PIPELINE_CONFIG = {
    "model_writeup": "o1-preview-2024-09-12",
    "model_citation": "gpt-4o-2024-11-20",
    "model_review": "gpt-4o-2024-11-20",
    "model_agg_plots": "o3-mini-2025-01-31",
    "writeup_type": "icbinb",
    "add_dataset_ref": False,
    "load_code": False,
    "attempt_id": 0,
    "num_cite_rounds": 20,
}


st.set_page_config(
    page_title="AI Scientist Orchestrator",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    [data-testid="stSidebar"][aria-expanded="true"] {
        min-width: 420px;
        width: 420px;
    }
    [data-testid="stSidebar"][aria-expanded="false"] {
        margin-left: -420px;
    }
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 999px;
        background: #eef2ff;
        color: #1f2937;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .log-textarea textarea {
        font-family: "Roboto Mono", "Courier New", monospace;
        font-size: 12px;
        line-height: 1.4;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def ensure_session_defaults() -> None:
    st.session_state.setdefault("current_view", "overview")
    st.session_state.setdefault("current_experiment", None)
    st.session_state.setdefault("auto_refresh", True)
    st.session_state.setdefault("pipeline_config", DEFAULT_PIPELINE_CONFIG.copy())
    st.session_state.setdefault(
        "idea_form",
        {
            "name": "",
            "title": "",
            "kw": "",
            "tldr": "",
            "abs": "",
        },
    )
    st.session_state.setdefault("stakeholder_summaries", {})


def go_to_overview() -> None:
    st.session_state["current_view"] = "overview"
    st.session_state["current_experiment"] = None


def go_to_experiment(exp_name: str) -> None:
    st.session_state["current_view"] = "experiment"
    st.session_state["current_experiment"] = exp_name


def auto_refresh_if_needed() -> None:
    if st.session_state.get("auto_refresh", True):
        try:
            st.query_params["refresh"] = str(int(time.time() // AUTO_REFRESH_SECONDS))
        except Exception:
            pass


def get_snapshot(name: str, snapshots: Iterable[ExperimentSnapshot]) -> Optional[ExperimentSnapshot]:
    for snapshot in snapshots:
        if snapshot.name == name:
            return snapshot
    return None


def render_sidebar(snapshots: Iterable[ExperimentSnapshot]) -> None:
    st.sidebar.title("AI Scientist Control")
    st.sidebar.checkbox(
        "Auto refresh every 5s",
        value=st.session_state.get("auto_refresh", True),
        key="auto_refresh",
    )
    st.sidebar.button("Overview", on_click=go_to_overview, use_container_width=True)

    snapshots = list(snapshots)
    if snapshots:
        st.sidebar.subheader("Experiments")
        current = st.session_state.get("current_experiment")
        names = [snap.name for snap in snapshots]
        index = names.index(current) if current in names else 0
        selected = st.sidebar.selectbox(
            "Jump to experiment",
            names,
            index=index,
            key="sidebar_experiment_select",
        )
        st.sidebar.button(
            "Open detail page",
            on_click=partial(go_to_experiment, selected),
            use_container_width=True,
        )
    else:
        st.sidebar.info("No experiments yet.")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Quick Deployment")
    deploy_endpoint = st.sidebar.text_input("RunPod endpoint ID", key="deploy_endpoint")
    deploy_api_key = st.sidebar.text_input("RunPod API Key", type="password", key="deploy_api_key")
    deploy_payload = st.sidebar.text_area("Deployment payload (JSON)", value="{}", key="deploy_payload")
    if st.sidebar.button("Deploy latest best solution", use_container_width=True):
        _deploy_latest_best_solution(snapshots, deploy_api_key, deploy_endpoint, deploy_payload)


def _deploy_latest_best_solution(
    snapshots: Iterable[ExperimentSnapshot],
    api_key: str,
    endpoint_id: str,
    input_json: str,
) -> None:
    if not api_key or not endpoint_id:
        st.sidebar.error("Provide both API key and endpoint ID.")
        return
    snapshots = list(snapshots)
    if not snapshots:
        st.sidebar.error("No experiments available for deployment.")
        return
    latest = snapshots[0]
    best_files = sorted(latest.path.glob("logs/**/best_solution_*.py"))
    if not best_files:
        st.sidebar.error(f"No best_solution_*.py found in {latest.name}.")
        return
    script_path = best_files[-1]
    try:
        response = deploy_to_runpod(api_key, endpoint_id, str(script_path), input_json)
        st.sidebar.success(f"Deployment triggered: {response}")
    except Exception as exc:
        st.sidebar.error(f"Deployment failed: {exc}")


def render_idea_studio(ideas: Iterable[IdeaDocument]) -> None:
    ideas = list(ideas)
    st.header("Idea Studio")
    st.caption("Generate fresh experiments, review proposals, and launch the full AI Scientist pipeline.")

    if not ideas:
        st.warning("No idea workshops found. Create one below to get started.")

    with st.expander("Create new workshop (.md)", expanded=False):
        render_idea_creation_form()

    if ideas:
        slugs = [doc.slug for doc in ideas]
        index = slugs.index(st.session_state.get("selected_idea_slug")) if st.session_state.get("selected_idea_slug") in slugs else 0
        selected_slug = st.selectbox("Select idea workshop", slugs, index=index, key="selected_idea_slug")
        selected_doc = next(doc for doc in ideas if doc.slug == selected_slug)

        metadata_cols = st.columns([2, 1])
        with metadata_cols[0]:
            st.subheader(selected_doc.display_name)
            if selected_doc.keywords:
                st.write("**Keywords:** " + ", ".join(selected_doc.keywords))
            if selected_doc.tldr:
                st.write(f"**TL;DR:** {selected_doc.tldr}")
            if selected_doc.abstract:
                st.markdown("**Abstract**")
                st.write(selected_doc.abstract)
        with metadata_cols[1]:
            st.markdown("**Files**")
            st.code(str(selected_doc.md_path))
            if selected_doc.json_path.exists():
                st.code(str(selected_doc.json_path))
            else:
                st.caption("Idea proposals will be written to the matching .json file.")

        ideation_cols = st.columns([2, 1])
        with ideation_cols[0]:
            render_ideation_controls(selected_doc)
        with ideation_cols[1]:
            render_ideation_log(selected_doc)

        if selected_doc.has_proposals:
            st.subheader("Review generated proposals")
            render_proposal_selector(selected_doc)
            st.subheader("Launch experiment from selected proposal")
            render_pipeline_launcher(selected_doc)
        else:
            st.info("Run ideation to populate proposals, or drop an existing .json next to the workshop file.")


def render_idea_creation_form() -> None:
    form = st.form("create_idea_form")
    name = form.text_input("File name (no spaces, .md auto-appended)", key="new_idea_name", value=st.session_state.idea_form["name"])
    title = form.text_input("Title", key="new_idea_title", value=st.session_state.idea_form["title"])
    keywords = form.text_input("Keywords (comma separated)", key="new_idea_kw", value=st.session_state.idea_form["kw"])
    tldr = form.text_area("TL;DR", key="new_idea_tldr", value=st.session_state.idea_form["tldr"], height=120)
    abstract = form.text_area("Abstract", key="new_idea_abs", value=st.session_state.idea_form["abs"], height=160)
    submitted = form.form_submit_button("Create Idea File")
    if submitted:
        try:
            created_path = utils.create_idea_file(
                filename=name.strip(),
                title=title.strip(),
                keywords=[kw.strip() for kw in keywords.split(",") if kw.strip()],
                tldr=tldr.strip(),
                abstract=abstract.strip(),
            )
            st.success(f"Created {created_path}")
            st.experimental_rerun()
        except Exception as exc:
            st.error(f"Failed to create idea: {exc}")


def render_ideation_controls(doc: IdeaDocument) -> None:
    with st.form(f"ideation_form_{doc.slug}"):
        model = st.text_input("Model for ideation", value="gpt-5", help="Used for idea generation")
        max_generations = st.number_input("Max generations", min_value=1, value=20)
        reflections = st.number_input("Reflections", min_value=1, value=5)
        submitted = st.form_submit_button("Generate proposals", use_container_width=True)
        if submitted:
            if not doc.md_path.exists():
                st.error("Workshop file missing, cannot run ideation.")
                return
            try:
                utils.spawn_ideation(
                    workshop_file=str(doc.md_path),
                    model=model,
                    max_num_generations=int(max_generations),
                    num_reflections=int(reflections),
                )
                st.success(f"Ideation started. Monitoring log: /tmp/ideation_{doc.slug}.log")
            except Exception as exc:
                st.error(f"Failed to launch ideation: {exc}")


def render_ideation_log(doc: IdeaDocument) -> None:
    log_path = LOG_ROOT / f"ideation_{doc.slug}.log"
    if log_path.exists():
        st.caption("Recent ideation log")
        st.text_area(
            "Last 100 lines",
            read_log_tail(log_path, max_lines=100),
            height=220,
            key=f"ideation_log_{doc.slug}",
        )
    else:
        st.caption("Ideation log will stream here after the next run.")


def render_proposal_selector(doc: IdeaDocument) -> None:
    proposal_titles = [proposal.display_title for proposal in doc.proposals]
    default_index = min(st.session_state.get(f"proposal_index_{doc.slug}", 0), len(proposal_titles) - 1)
    selected_index = st.radio(
        "Choose a proposal to launch",
        options=list(range(len(proposal_titles))),
        format_func=lambda idx: proposal_titles[idx],
        index=default_index,
        key=f"proposal_selector_{doc.slug}",
    )
    st.session_state[f"proposal_index_{doc.slug}"] = selected_index
    proposal = doc.proposals[selected_index]

    st.markdown(f"**Short hypothesis**: {proposal.summary or 'n/a'}")
    if proposal.experiments:
        st.markdown("**Experiment plan**")
        st.markdown(proposal.experiments)
    if proposal.abstract:
        with st.expander("Abstract"):
            st.write(proposal.abstract)


def render_pipeline_launcher(doc: IdeaDocument) -> None:
    config = st.session_state["pipeline_config"]
    with st.form(f"pipeline_launcher_{doc.slug}"):
        writeup_model = st.text_input("model_writeup", value=config["model_writeup"])
        citation_model = st.text_input("model_citation", value=config["model_citation"])
        review_model = st.text_input("model_review", value=config["model_review"])
        agg_model = st.text_input("model_agg_plots", value=config["model_agg_plots"])
        cols = st.columns(3)
        with cols[0]:
            writeup_type = st.selectbox("writeup_type", ["icbinb", "normal"], index=0 if config["writeup_type"] == "icbinb" else 1)
        with cols[1]:
            add_dataset = st.checkbox("Add HF dataset reference", value=config["add_dataset_ref"])
            load_code = st.checkbox("Load .py with same name", value=config["load_code"])
        with cols[2]:
            attempt_id = st.number_input("Attempt id", min_value=0, value=int(config["attempt_id"]))
            num_rounds = st.number_input("Citation rounds", min_value=1, value=int(config["num_cite_rounds"]))

        submitted = st.form_submit_button("Launch AI Scientist pipeline", use_container_width=True)
        if submitted:
            target_path = doc.json_path if doc.json_path.exists() else doc.md_path.with_suffix(".json")
            try:
                utils.spawn_pipeline(
                    idea_json_path=str(target_path),
                    writeup_type=writeup_type,
                    add_dataset_ref=add_dataset,
                    load_code=load_code,
                    attempt_id=int(attempt_id),
                    model_writeup=writeup_model,
                    model_citation=citation_model,
                    model_review=review_model,
                    model_agg_plots=agg_model,
                    num_cite_rounds=int(num_rounds),
                )
                st.session_state["pipeline_config"] = {
                    "model_writeup": writeup_model,
                    "model_citation": citation_model,
                    "model_review": review_model,
                    "model_agg_plots": agg_model,
                    "writeup_type": writeup_type,
                    "add_dataset_ref": add_dataset,
                    "load_code": load_code,
                    "attempt_id": int(attempt_id),
                    "num_cite_rounds": int(num_rounds),
                }
                log_name = f"pipeline_{target_path.stem}_attempt_{int(attempt_id)}"
                st.success(f"Pipeline launched. Tail logs with: tail -f /tmp/{log_name}.log")
            except Exception as exc:
                st.error(f"Failed to launch pipeline: {exc}")


def render_experiment_overview(snapshots: Iterable[ExperimentSnapshot]) -> None:
    snapshots = list(snapshots)
    st.header("Experiments Overview")
    if not snapshots:
        st.info("No experiments yet. Launch one from the Idea Studio above.")
        return

    running = [snap for snap in snapshots if snap.is_running]
    latest_update = snapshots[0].last_updated or snapshots[0].started_at
    metric_cols = st.columns(4)
    metric_cols[0].metric("Total experiments", len(snapshots))
    metric_cols[1].metric("Active runs", len(running))
    metric_cols[2].metric(
        "Avg progress",
        f"{int(sum([snap.progress_ratio or 0 for snap in snapshots]) / len(snapshots) * 100)}%",
    )
    metric_cols[3].metric(
        "Latest update",
        latest_update.strftime("%Y-%m-%d %H:%M:%S") if latest_update else "n/a",
    )

    for snapshot in snapshots:
        render_experiment_card(snapshot)


def render_experiment_card(snapshot: ExperimentSnapshot) -> None:
    card = st.container()
    status_icon = "🟢" if snapshot.is_running else ("✅" if (snapshot.progress_ratio or 0) >= 1 else "🕒")
    with card:
        st.markdown(f"### {status_icon} {snapshot.name}")
        sub_cols = st.columns([2, 1])
        with sub_cols[0]:
            st.caption(f"Idea: {snapshot.idea_slug or 'unknown'}")
            if snapshot.started_at:
                st.caption(f"Started: {snapshot.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
            if snapshot.progress_ratio is not None:
                st.progress(min(max(snapshot.progress_ratio, 0.0), 1.0))
            st.write(snapshot.status_text)
            if snapshot.latest_note:
                st.info(snapshot.latest_note)
        with sub_cols[1]:
            st.metric("Good nodes", snapshot.metrics["good_nodes"])
            st.metric("Buggy nodes", snapshot.metrics["buggy_nodes"])
            artifact_summary = ", ".join(
                f"{key}:{val}" for key, val in snapshot.artifact_counts.items() if val
            )
            st.caption(f"Artifacts: {artifact_summary or 'pending'}")
            st.button(
                "View details",
                key=f"open_{snapshot.name}",
                on_click=partial(go_to_experiment, snapshot.name),
                use_container_width=True,
            )
        st.markdown("---")


def render_experiment_page(snapshot: ExperimentSnapshot, ideas: Iterable[IdeaDocument]) -> None:
    st.title(f"Experiment · {snapshot.name}")
    idea_doc = next((doc for doc in ideas if doc.slug == snapshot.idea_slug), None)
    caption_parts = []
    if snapshot.idea_slug:
        caption_parts.append(f"Idea: {snapshot.idea_slug}")
    if snapshot.started_at:
        caption_parts.append(f"Started {snapshot.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    st.caption(" · ".join(caption_parts))

    progress_cols = st.columns(4)
    progress_cols[0].metric("Progress", f"{snapshot.progress_percent or 0}%")
    progress_cols[1].metric("Stage", snapshot.current_stage or "pending")
    progress_cols[2].metric("Good nodes", snapshot.metrics["good_nodes"])
    progress_cols[3].metric("Buggy nodes", snapshot.metrics["buggy_nodes"])
    if snapshot.progress_ratio is not None:
        st.progress(min(max(snapshot.progress_ratio, 0.0), 1.0))

    render_stakeholder_summary(snapshot, idea_doc)

    tabs = st.tabs(["Timeline", "Artifacts", "Logs", "Raw data"])

    with tabs[0]:
        render_stage_timeline(snapshot)
    with tabs[1]:
        render_artifacts(snapshot)
    with tabs[2]:
        render_log_panel(snapshot)
    with tabs[3]:
        render_raw_snapshot(snapshot)


def render_stakeholder_summary(snapshot: ExperimentSnapshot, idea_doc: Optional[IdeaDocument]) -> None:
    st.subheader("Stakeholder Summary")
    summary_store: Dict[str, str] = st.session_state["stakeholder_summaries"]
    if summary_store.get(snapshot.name):
        st.success(summary_store[snapshot.name])
    else:
        st.info("Generate a concise stakeholder-friendly update summarizing progress and next steps.")
    if st.button("Generate Stakeholder Summary", key=f"summarize_{snapshot.name}"):
        with st.spinner("Summarizing latest progress via LLM..."):
            try:
                summary_store[snapshot.name] = build_stakeholder_summary(snapshot, idea_doc)
            except Exception as exc:
                st.error(f"Failed to generate summary: {exc}")


def build_stakeholder_summary(snapshot: ExperimentSnapshot, idea_doc: Optional[IdeaDocument]) -> str:
    model = "gpt-4o-mini"
    client, resolved_model = create_client(model)
    system_message = (
        "You are an operations lead writing crisp updates about AI research experiments. "
        "Summaries must stay high-level, highlight progress, current activity, and immediate focus. "
        "Keep bullets short and avoid jargon."
    )
    idea_context = ""
    if idea_doc:
        idea_context = f"Idea title: {idea_doc.display_name}\nTLDR: {idea_doc.tldr}\n"
    stages_lines = []
    for stage in snapshot.stage_details:
        name = stage.get("name", "stage")
        good = stage.get("good_nodes", 0)
        buggy = stage.get("buggy_nodes", 0)
        note = stage.get("notes") or stage.get("latest_node_summary")
        note_text = ""
        if isinstance(note, str):
            note_text = note
        elif isinstance(note, dict):
            note_text = note.get("summary") or note.get("note") or ""
        stages_lines.append(f"- {name}: good={good}, buggy={buggy}, note={note_text}")
    prompt = (
        f"{idea_context}"
        f"Experiment name: {snapshot.name}\n"
        f"Progress percent: {snapshot.progress_percent or 0}\n"
        f"Current stage: {snapshot.current_stage or 'pending'}\n"
        f"Status text: {snapshot.status_text}\n"
        f"Latest note: {snapshot.latest_note or ''}\n"
        f"Stages:\n" + "\n".join(stages_lines)
    )
    summary, _ = get_response_from_llm(
        prompt=prompt,
        client=client,
        model=resolved_model,
        system_message=system_message,
        temperature=0.3,
    )
    return summary.strip()


def render_stage_timeline(snapshot: ExperimentSnapshot) -> None:
    if not snapshot.stage_details:
        st.info("Stage updates will appear here once the pipeline starts emitting progress.")
        return
    for stage in snapshot.stage_details:
        header = stage.get("name", "Stage")
        total = stage.get("total_nodes", 0)
        good = stage.get("good_nodes", 0)
        buggy = stage.get("buggy_nodes", 0)
        label = f"{header} · total {total} · good {good} · buggy {buggy}"
        with st.expander(label, expanded=(stage is snapshot.stage_details[-1])):
            if stage.get("best_metric"):
                st.markdown("**Best metric**")
                st.code(str(stage["best_metric"]))
            note = stage.get("notes")
            if isinstance(note, str) and note.strip():
                st.markdown("**Stage notes**")
                st.write(note)
            latest_node = stage.get("latest_node_summary")
            if isinstance(latest_node, dict) and latest_node:
                st.markdown("**Latest node summary**")
                st.json(latest_node)


def render_artifacts(snapshot: ExperimentSnapshot) -> None:
    artifacts = snapshot.artifacts
    if not any(
        [
            artifacts.get("figures"),
            artifacts.get("experiment_plots"),
            artifacts.get("tree_html"),
            artifacts.get("pdf"),
        ]
    ):
        st.info("Artifacts will arrive as the experiment finishes evaluation stages.")
        return

    if artifacts.get("experiment_plots"):
        st.markdown("**Live experiment plots**")
        cols = st.columns(2)
        for idx, plot in enumerate(artifacts["experiment_plots"][:10]):
            with cols[idx % 2]:
                st.image(str(plot), use_container_width=True, caption=plot.name)
    if artifacts.get("figures"):
        st.markdown("**Final aggregated figures**")
        cols = st.columns(3)
        for idx, figure in enumerate(artifacts["figures"]):
            with cols[idx % 3]:
                st.image(str(figure), use_container_width=True, caption=figure.name)
    tree_html = artifacts.get("tree_html")
    if tree_html and tree_html.exists():
        st.markdown("**Search tree visualization**")
        st.components.v1.html(tree_html.read_text(errors="ignore"), height=700, scrolling=True)
    pdf = artifacts.get("pdf")
    if pdf and pdf.exists():
        with open(pdf, "rb") as pdf_file:
            st.download_button("Download PDF", pdf_file, file_name=pdf.name)


def render_log_panel(snapshot: ExperimentSnapshot) -> None:
    if snapshot.log_path:
        log_tail = read_log_tail(snapshot.log_path, max_lines=200)
        if log_tail:
            st.text_area(
                "Recent pipeline logs (last 200 lines)",
                value=log_tail,
                height=400,
                key=f"log_text_{snapshot.name}",
                help=str(snapshot.log_path),
            )
        else:
            st.info(f"Log file exists but is empty: {snapshot.log_path}")
    else:
        st.info("Pipeline log not yet available for this experiment.")


def render_raw_snapshot(snapshot: ExperimentSnapshot) -> None:
    st.json(
        {
            "name": snapshot.name,
            "idea_slug": snapshot.idea_slug,
            "attempt_id": snapshot.attempt_id,
            "started_at": snapshot.started_at.isoformat() if snapshot.started_at else None,
            "status_text": snapshot.status_text,
            "progress_ratio": snapshot.progress_ratio,
            "current_stage": snapshot.current_stage,
            "metrics": snapshot.metrics,
            "artifact_counts": snapshot.artifact_counts,
            "log_path": str(snapshot.log_path) if snapshot.log_path else None,
            "latest_note": snapshot.latest_note,
        }
    )


def main() -> None:
    ensure_session_defaults()
    auto_refresh_if_needed()

    ideas = load_all_ideas()
    snapshots = load_experiment_snapshots()

    render_sidebar(snapshots)

    current_view = st.session_state.get("current_view", "overview")
    current_experiment = st.session_state.get("current_experiment")

    if current_view == "experiment" and current_experiment:
        snapshot = get_snapshot(current_experiment, snapshots)
        if snapshot:
            render_experiment_page(snapshot, ideas)
        else:
            st.warning("Experiment not found, returning to overview.")
            go_to_overview()
            render_overview(ideas, snapshots)
    else:
        render_overview(ideas, snapshots)


def render_overview(ideas: Iterable[IdeaDocument], snapshots: Iterable[ExperimentSnapshot]) -> None:
    st.title("AI Scientist Orchestrator")
    render_idea_studio(ideas)
    render_experiment_overview(snapshots)


if __name__ == "__main__":
    main()
