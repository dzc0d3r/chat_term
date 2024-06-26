#!/usr/bin/env python
import os
import json
from typing_extensions import Literal
from openai import AsyncOpenAI
import pyperclip
from textual.binding import Binding
from textual import work
from textual.app import App, ComposeResult
from textual.widgets import Footer, Static, Markdown, TextArea, Label

from textual.containers import VerticalScroll
from textual import events
from textual.reactive import var


# stores chat history until reset.
SESSION_CONTEXT = {
    "role": "system",
    "content": "",
}

try:
    BASE_PATH = os.path.dirname(__file__)
except NameError:
    BASE_PATH = os.getcwd()

with open(os.path.join(BASE_PATH, "config.jsonc")) as fp:
    lines = fp.readlines()
    json_str = "".join([line for line in lines if not line.lstrip().startswith("//")])
    CONFIG = json.loads(json_str)


def copy_to_clipboard(text):
    """Copy text to clipboard; return True if successful."""
    try:
        pyperclip.copy(text)
    except Exception as e:
        print(e, "copy to clipboard failed")
        return False
    return True


def get_key():
    """Return the open ai api key."""
    secrets_file = os.path.join(BASE_PATH, "secrets.json")
    with open(secrets_file) as fp:
        secrets = json.load(fp)
        api_key = secrets.get("API_KEY")
        if not api_key:
            raise Exception("you must provide your API_KEY in secrets.json")
    return api_key

def get_base_url():
    """Return the open ai api key."""
    secrets_file = os.path.join(BASE_PATH, "secrets.json")
    with open(secrets_file) as fp:
        secrets = json.load(fp)
        base_url = secrets.get("BASE_URL")
    return base_url
def get_model():
    """Return the open ai api key."""
    secrets_file = os.path.join(BASE_PATH, "secrets.json")
    with open(secrets_file) as fp:
        secrets = json.load(fp)
        model = secrets.get("MODEL")
    return model


class InputText(Static):
    """Formatted widget that contains prompt text."""

    pass


class ResponseText(Markdown):
    """Formatted widget that contains response text."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._text = ""

    def on_click(self) -> None:
        """Visual feedback if copy successful"""
        copied = copy_to_clipboard(self._text)
        if copied:
            self.styles.opacity = 0.0
            self.styles.animate(
                attribute="opacity", value=1.0, duration=0.3, easing="out_expo"
            )

    async def append_text(self, new_text):
        self._text += new_text
        await self.update(self._text)

    def clear_text(self):
        self._text = ""
        self.update(self._text)


class MyTextArea(TextArea):
    BINDINGS = [tuple(k) for k in CONFIG["keybindings"]] + [
        Binding("ctrl+c", "", "", show=False)
    ]
    height = 3
    

    def action_input_focus(self):
        """Scroll up in response text."""
        widget = self.my_text_area
        widget.focus()
    
    def on_key(self, event: events.Key) -> None:
        if event.key == "ctrl+c":
            self.app.exit()
        


        


class ChatApp(App):
    """chat TUI"""

    def __init__(self):
        super().__init__()
        
        self.my_text_area = MyTextArea(id="input", soft_wrap=True).code_editor(
            theme="dracula", language="markdown", soft_wrap=True,
            show_line_numbers=True, id="editor", 
        )  
        # Instantiate MyTextArea and keep a reference
        

    CSS_PATH = "chat.css"
    BINDINGS = [tuple(k) for k in CONFIG["keybindings"]] + [
        Binding("ctrl+c", "", "", show=False),
        Binding("j", "scroll_down"),
        Binding("k", "scroll_up"),
        Binding("i", "input_focus"),

    ]
    def action_scroll_up(self):
        """Scroll up in response text."""
        response_text = self.query_one("#content_window")
        
        response_text.scroll_up()

    def action_scroll_down(self):
        """Scroll down in response text."""
        response_text = self.query_one("#content_window")
        response_text.scroll_down()

    def action_input_focus(self):
        """Scroll up in response text."""
        widget = self.my_text_area
        widget.focus()

    chat_history = [SESSION_CONTEXT]

    expanded_input = var(False)

    def watch_expanded_input(self, expanded_input: bool) -> None:
        """Called when expanded_input is modified."""
        self.set_class(expanded_input, "-expanded-input")

    def action_toggle_input(self) -> None:
        """Toggle expanded input."""
        self.expanded_input = not self.expanded_input

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="content_window"):
            yield InputText(id="results")        
        yield Label("Enter your message:", id="prompt-label") 
        yield self.my_text_area
        yield Footer()

    def on_mount(self) -> None:
        """Called when app starts."""
        # Give the input focus, so we can start typing straight away
        self.my_text_area.focus()

    def action_focus_input(self) -> None:
        
        self.my_text_area.focus()

    def action_reset_chat_session(self) -> None:
        self.chat_history = [SESSION_CONTEXT]
        window = self.query_one("#content_window")
        window.query("InputText").remove()
        window.query("ResponseText").remove()
        input_widget = self.my_text_area
        input_widget.load_text("")
        input_widget.focus()

    def action_add_query(self, query_str) -> None:
        """Add next query section."""
        self.chat_history.append({"role": "user", "content": query_str})
        #input_widget = self.query_one("#input", MyTextArea).load_text("")
        query_text = InputText("󰜴 You : " + query_str)
        content_window = self.query_one("#content_window", VerticalScroll)
        content_window.mount(query_text)
        query_text.scroll_visible()
        return query_text

    def action_add_response(self) -> None:
        """Add next response section."""
        response_text = ResponseText("Model 🤖 ...")
        content_window = self.query_one("#content_window", VerticalScroll)
        self.query_one("#content_window").mount(response_text)
        response_text.scroll_visible()
        return response_text
    

    async def action_submit(self) -> None:
        """Submit chat text."""
        widget = self.my_text_area
        query_str = widget.text
        if query_str:
            widget.clear()
            self.issue_query(query_str)
            response_text = self.query_one("#content_window").query("ResponseText")
            widget.blur()
            response_text.focus()
            
        else:
            pass

    @work(exclusive=True)
    async def issue_query(self, query_str: str) -> None:
        """Query chat gpt."""
        self.action_add_query(query_str=query_str)
        response_text = self.action_add_response()
        current_response = ""
        client = AsyncOpenAI(api_key=get_key(), base_url=get_base_url())
        stream = await client.chat.completions.create(
            messages=self.chat_history,
            model=get_model(),
            stream=True,
        )
        async for part in stream:
            content = part.choices[0].delta.content or ""
            if content is not None:
                current_response += content
                
                await response_text.append_text(content)
                

        if current_response is not None:
            self.chat_history.append(
                {"role": "assistant", "content": str(current_response)}
            )


if __name__ == "__main__":
    app = ChatApp()
    app.run()
