import gradio as gr
import json
import os
from modules import script_callbacks
from pathlib import Path

# Configuration - Use relative paths for cross-platform compatibility
EXT_DIR = Path(__file__).parent.parent
ACTION_JSON_PATH = EXT_DIR / "action.json"
WILDCARD_DIR = Path("extensions/sd-dynamic-prompts/wildcards")


class PromptHelperExtension:
    def __init__(self):
        self.action_data = {}
        self.wildcard_files = []
        self.session_state = {}
        self.load_data()

    def load_data(self):
        """Load action.json and wildcard files with nested folder support"""
        try:
            if ACTION_JSON_PATH.exists():
                with open(ACTION_JSON_PATH, 'r', encoding='utf-8') as f:
                    self.action_data = json.load(f)
        except Exception as e:
            print(f"Error loading action.json: {e}")
            self.action_data = {}

        try:
            self.wildcard_files = []
            if WILDCARD_DIR.exists():
                for file_path in WILDCARD_DIR.rglob("*.txt"):
                    relative_path = file_path.relative_to(WILDCARD_DIR)
                    wildcard_name = str(relative_path.with_suffix('')).replace(os.sep, "/")
                    self.wildcard_files.append(wildcard_name)
            self.wildcard_files.sort()
        except Exception as e:
            print(f"Error loading wildcard files: {e}")
            self.wildcard_files = []

    def _get_state(self, session_id: str):
        if session_id not in self.session_state:
            self.session_state[session_id] = {"last_injected": ""}
        return self.session_state[session_id]

    def _build_injected(self, actions_selected, wildcards_selected):
        """Build the exact injected substring"""
        action_texts = [self.action_data[a] for a in actions_selected if a in self.action_data]
        wildcard_texts = [f"__{w}__" for w in wildcards_selected]
        items = [s for s in (action_texts + wildcard_texts) if s]
        return ", ".join(items)

    def _strip_previous_block(self, prompt: str, previous_block: str):
        """Remove the previously injected block and adjacent commas/spaces"""
        if not prompt or not previous_block:
            return prompt.strip()

        idx = prompt.rfind(previous_block)
        if idx == -1:
            return prompt.strip().strip(", ")

        start = idx
        end = idx + len(previous_block)

        # Expand backwards to remove leading comma/space
        while start > 0 and prompt[start - 1] == ' ':
            start -= 1
        if start > 0 and prompt[start - 1] == ',':
            start -= 1
            while start > 0 and prompt[start - 1] == ' ':
                start -= 1

        # Trim trailing spaces/commas
        while end < len(prompt) and prompt[end] == ' ':
            end += 1
        if end < len(prompt) and prompt[end] == ',':
            end += 1
            while end < len(prompt) and prompt[end] == ' ':
                end += 1

        new_prompt = (prompt[:start] + prompt[end:]).strip()
        return new_prompt.strip(", ").strip()

    def apply_selection(self, current_prompt: str, actions_selected, wildcards_selected, session_id: str):
        """Remove old injected block, append new block"""
        state = self._get_state(session_id)
        prev = state["last_injected"] or ""

        base = self._strip_previous_block(current_prompt or "", prev)
        new_block = self._build_injected(actions_selected, wildcards_selected)

        if base and new_block:
            out = f"{base}, {new_block}"
        elif new_block:
            out = new_block
        else:
            out = base

        state["last_injected"] = new_block
        return out


# Global instance
prompt_helper = PromptHelperExtension()
txt2img_prompt_component = None
img2img_prompt_component = None


def create_dropdown_menus(prompt_type, prompt_component):
    """Create dropdown menus under Styles selection"""
    with gr.Box(elem_id=f"{prompt_type}_prompt_helper_container"):
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("**Actions**")
                action_dropdown = gr.Dropdown(
                    choices=list(prompt_helper.action_data.keys()),
                    value=[],
                    elem_id=f"{prompt_type}_action_dropdown",
                    interactive=True,
                    multiselect=True,
                    show_label=False
                )
            with gr.Column(scale=1):
                gr.Markdown("**Wildcards**")
                wildcard_dropdown = gr.Dropdown(
                    choices=prompt_helper.wildcard_files,
                    value=[],
                    elem_id=f"{prompt_type}_wildcard_dropdown",
                    interactive=True,
                    multiselect=True,
                    show_label=False
                )

    session_id = f"{prompt_type}_{id(prompt_component)}"

    def on_change(actions, wildcards, prompt):
        return prompt_helper.apply_selection(prompt, actions, wildcards, session_id)

    action_dropdown.change(
        fn=on_change,
        inputs=[action_dropdown, wildcard_dropdown, prompt_component],
        outputs=prompt_component,
        show_progress=False
    )
    wildcard_dropdown.change(
        fn=on_change,
        inputs=[action_dropdown, wildcard_dropdown, prompt_component],
        outputs=prompt_component,
        show_progress=False
    )


def capture_prompt_components(component, **kwargs):
    """Capture prompt components for later use"""
    global txt2img_prompt_component, img2img_prompt_component
    if kwargs.get("elem_id") == "txt2img_prompt":
        txt2img_prompt_component = component
    elif kwargs.get("elem_id") == "img2img_prompt":
        img2img_prompt_component = component


def inject_dropdowns(prompt_type):
    """Inject dropdowns under the Styles menu"""
    def callback(component, **kwargs):
        if kwargs.get("elem_id") == f"{prompt_type}_styles":
            prompt_component = txt2img_prompt_component if prompt_type == "txt2img" else img2img_prompt_component
            if prompt_component is not None:
                create_dropdown_menus(prompt_type, prompt_component)
    return callback


# Register callbacks
script_callbacks.on_after_component(capture_prompt_components)
script_callbacks.on_after_component(inject_dropdowns("txt2img"))
script_callbacks.on_after_component(inject_dropdowns("img2img"))


# Dummy callbacks
def on_ui_tabs():
    pass

def on_ui_settings():
    pass

script_callbacks.on_ui_tabs(on_ui_tabs)
script_callbacks.on_ui_settings(on_ui_settings)