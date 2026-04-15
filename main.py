import asyncio
import json
import re
import random
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import os

API_SECRET_KEY = os.getenv("API_SECRET_KEY", "change-secret-key-2026")

GEMINI_URL     = "https://gemini.google.com/app"
INPUT_SELECTOR = 'div[role="textbox"], rich-textarea .ql-editor, textarea'
SEND_SELECTOR  = 'button[aria-label="Send message"], button[data-test-id="send-button"]'
STOP_SELECTORS = [
    'button[aria-label="Stop response"]',
    'button[aria-label="Stop generating"]',
    'button[aria-label="Cancel"]',
    '[data-test-id="stop-button"]',
]


class AsyncBrowserEngine:
    def __init__(self):
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.playwright = None
        self._page: Page = None
        self._lock = asyncio.Lock()
        self._ready = asyncio.Event()

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-notifications",
                "--mute-audio",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )

        self._page = await self.context.new_page()
        await self._page.goto(GEMINI_URL, wait_until="domcontentloaded")
        await asyncio.sleep(random.uniform(3, 5))
        await self._page.wait_for_selector(INPUT_SELECTOR, timeout=60_000)

        self._ready.set()
        print("[SERVER] Browser is ready and page is loaded")

    async def _hard_refresh(self):
        print("[SERVER] Hard refresh...")
        await self._page.evaluate("location.reload(true)")
        await self._page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(random.uniform(2, 4))
        await self._page.wait_for_selector(INPUT_SELECTOR, timeout=30_000)
        print("[SERVER] Page reloaded and ready for next input")

    async def _talk_to_gemini(self, prompt: str) -> str:
        page = self._page

        await page.wait_for_selector(INPUT_SELECTOR, timeout=30_000)
        await page.click(INPUT_SELECTOR)
        await page.fill(INPUT_SELECTOR, prompt)
        await asyncio.sleep(1.0)

        initial_count = await page.locator("model-response").count()

        try:
            send_btn = page.locator(SEND_SELECTOR).first
            await send_btn.wait_for(state="visible", timeout=5_000)
            await send_btn.click()
        except Exception:
            await page.keyboard.press("Enter")

        for _ in range(60):
            if await page.locator("model-response").count() > initial_count:
                break
            await asyncio.sleep(0.5)
        else:
            raise TimeoutError("Error: No response detected after sending the prompt")

        stop_appeared = False
        for _ in range(20):
            for sel in STOP_SELECTORS:
                try:
                    if await page.locator(sel).first.is_visible():
                        stop_appeared = True
                        break
                except Exception:
                    pass
            if stop_appeared:
                break
            await asyncio.sleep(0.5)

        if stop_appeared:
            for _ in range(240):
                still_going = False
                for sel in STOP_SELECTORS:
                    try:
                        if await page.locator(sel).first.is_visible():
                            still_going = True
                            break
                    except Exception:
                        pass
                if not still_going:
                    break
                await asyncio.sleep(0.5)
        else:
            last_text, stable = "", 0
            for _ in range(120):
                try:
                    cnt = await page.locator("model-response").count()
                    if cnt > 0:
                        cur = await page.locator("model-response").nth(cnt - 1).inner_text()
                        if cur.strip() and cur == last_text:
                            stable += 1
                            if stable >= 5:
                                break
                        else:
                            last_text, stable = cur, 0
                except Exception:
                    pass
                await asyncio.sleep(0.5)

        await asyncio.sleep(1.0)

        responses = page.locator("model-response")
        cnt = await responses.count()
        if cnt == 0:
            raise ValueError("Error: No model-response elements found")

        last = responses.nth(cnt - 1)
        text = ""
        for sel in [".response-content", ".model-response-text", "message-content", ".markdown"]:
            try:
                inner = last.locator(sel)
                if await inner.count() > 0:
                    text = "\n".join(await inner.all_inner_texts()).strip()
                    if text:
                        break
            except Exception:
                continue

        if not text:
            text = await last.inner_text()

        result = text.strip()
        print(f"[SERVER] Response received ({len(result)} characters)")
        await self._hard_refresh()

        return result

    async def process_request(self, prompt: str) -> str:
        await self._ready.wait()
        async with self._lock:
            return await self._talk_to_gemini(prompt)


# ====================================================================
# Prompt Builder
# ====================================================================

def format_prompt(data):
    parts = []
    system_text = ""
    has_function_response = False

    system_instruction = data.get("systemInstruction")
    if system_instruction:
        sys_parts = system_instruction.get("parts", [])
        system_text = "\n".join(p.get("text", "") for p in sys_parts if "text" in p)

    for msg in data.get("contents", []):
        role = msg.get("role", "user")
        for part in msg.get("parts", []):
            if "text" in part:
                text = part["text"]
                parts.append(text if role == "user" else f"[Assistant]: {text}")
            elif "functionCall" in part:
                fc = part["functionCall"]
                parts.append(
                    f"[PREVIOUS TOOL CALL: Called '{fc.get('name','?')}' "
                    f"with: {json.dumps(fc.get('args',{}), ensure_ascii=False)}]"
                )
            elif "functionResponse" in part:
                has_function_response = True
                fr = part["functionResponse"]
                parts.append(
                    f"[TOOL RESULT from '{fr.get('name','tool')}']:\n"
                    f"{json.dumps(fr.get('response',{}), ensure_ascii=False)}"
                )

    function_declarations = []
    for tg in data.get("tools", []):
        function_declarations.extend(tg.get("functionDeclarations", []))

    final = ""
    if system_text:
        label = "YOUR ROLE" if (function_declarations and not has_function_response) else "SYSTEM INSTRUCTIONS"
        final += f"=== {label} ===\n{system_text}\n=== END ===\n\n"

    if function_declarations and not has_function_response:
        final += format_tools_instruction(function_declarations)

    if has_function_response:
        final += "=== CONTEXT FROM TOOLS ===\nUse ONLY this information to answer.\n\n"

    if parts:
        final += "\n".join(parts)

    if has_function_response:
        final += "\n\n=== INSTRUCTION ===\nAnswer ONLY based on the tool results above.\n"

    return final


def format_tools_instruction(function_declarations):
    instruction  = "\n=== MANDATORY TOOL USAGE ===\n"
    instruction += "You MUST use one of the tools below.\n"
    instruction += 'FORMAT: {"tool_calls": [{"name": "TOOL_NAME", "arguments": {"param": "value"}}]}\n\n'
    instruction += "Available tools:\n\n"
    for fd in function_declarations:
        name   = fd.get("name", "unknown")
        desc   = fd.get("description", "No description")
        params = fd.get("parameters", {})
        instruction += f"Tool: {name}\nDescription: {desc}\n"
        if params.get("properties"):
            req = params.get("required", [])
            instruction += "Parameters:\n"
            for pname, pinfo in params["properties"].items():
                instruction += (
                    f"  - {pname} ({pinfo.get('type','string')}, "
                    f"{'required' if pname in req else 'optional'}): "
                    f"{pinfo.get('description','')}\n"
                )
        instruction += "\n"
    instruction += "=== END OF TOOLS ===\n\n"
    first = function_declarations[0].get("name", "tool") if function_declarations else "tool"
    instruction += f'EXAMPLE: {{"tool_calls": [{{"name": "{first}", "arguments": {{"input": "..."}}}}]}}\n\nNow respond with the JSON:\n\n'
    return instruction


def parse_tool_calls_gemini(response_text):
    cleaned = response_text.strip()
    if "```" in cleaned:
        m = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', cleaned, re.DOTALL)
        if m:
            cleaned = m.group(1).strip()

    candidates = [cleaned]
    m2 = re.search(r'\{[\s\S]*"tool_calls"[\s\S]*\}', cleaned)
    if m2:
        candidates.append(m2.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and "tool_calls" in parsed:
                raw_calls = parsed["tool_calls"]
                if isinstance(raw_calls, list) and raw_calls:
                    fc_parts = []
                    for call in raw_calls:
                        args = call.get("arguments", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                args = {"input": args}
                        fc_parts.append({
                            "functionCall": {"name": call.get("name", ""), "args": args}
                        })
                    return fc_parts
        except Exception:
            continue
    return None


def get_api_key(request: Request) -> str:
    for key in [
        request.headers.get("x-goog-api-key", ""),
        request.query_params.get("key", ""),
    ]:
        if key:
            return key
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return ""


# ====================================================================
# FastAPI
# ====================================================================

browser_engine = AsyncBrowserEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await browser_engine.start()
    yield
    if browser_engine.context:
        await browser_engine.context.close()
    if browser_engine.browser:
        await browser_engine.browser.close()
    if browser_engine.playwright:
        await browser_engine.playwright.stop()


app = FastAPI(title="mse_ai_api Gemini Edition", lifespan=lifespan)


@app.post("/v1beta/models/{model_path:path}")
async def generate_content(model_path: str, request: Request):
    if ":generateContent" not in model_path:
        return JSONResponse(status_code=404, content={
            "error": {"code": 404, "message": f"Unknown method: {model_path}", "status": "NOT_FOUND"}
        })

    model_name = model_path.replace(":generateContent", "")

    if get_api_key(request) != API_SECRET_KEY:
        return JSONResponse(status_code=401, content={
            "error": {"code": 401, "message": "API key not valid.", "status": "UNAUTHENTICATED"}
        })

    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={
            "error": {"code": 400, "message": "Invalid JSON payload", "status": "INVALID_ARGUMENT"}
        })

    if not data.get("contents"):
        return JSONResponse(status_code=400, content={
            "error": {"code": 400, "message": "contents field is required", "status": "INVALID_ARGUMENT"}
        })

    function_declarations = []
    for tg in data.get("tools", []):
        function_declarations.extend(tg.get("functionDeclarations", []))

    try:
        prompt   = format_prompt(data)
        p_tokens = len(prompt.split())
        print(f"[SERVER] New request ({p_tokens} words) | Model: {model_name}")

        response_text   = await browser_engine.process_request(prompt)
        c_tokens        = len(response_text.split())
        tool_call_parts = parse_tool_calls_gemini(response_text) if function_declarations else None

        if tool_call_parts:
            candidates_content = {"parts": tool_call_parts, "role": "model"}
        else:
            candidates_content = {"parts": [{"text": response_text or ""}], "role": "model"}

        return {
            "candidates": [{"content": candidates_content, "finishReason": "STOP", "index": 0}],
            "usageMetadata": {
                "promptTokenCount": p_tokens,
                "candidatesTokenCount": c_tokens,
                "totalTokenCount": p_tokens + c_tokens,
            },
            "modelVersion": model_name,
        }

    except Exception as e:
        print(f"[SERVER] Error: {e}")
        return JSONResponse(status_code=500, content={
            "error": {"code": 500, "message": str(e), "status": "INTERNAL"}
        })


@app.get("/v1beta/models")
async def list_models():
    return {"models": [{
        "name": "models/gemini-3",
        "version": "3.0",
        "displayName": "Gemini 3",
        "description": "Multimodal AI model powered by mse_ai_api",
        "supportedGenerationMethods": ["generateContent", "countTokens"],
    }]}


@app.get("/v1beta/models/{model_name}")
async def get_model(model_name: str):
    return {
        "name": "models/gemini-3", "version": "3.0",
        "displayName": "Gemini 3",
        "description": "Multimodal AI model powered by mse_ai_api",
        "supportedGenerationMethods": ["generateContent", "countTokens"],
    }


@app.get("/")
async def health_check():
    return {"status": "running", "message": "mse_ai_api Gemini Server is active!"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9999)