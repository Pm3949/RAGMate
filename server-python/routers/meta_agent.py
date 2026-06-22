from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import json
import logging
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai import types
from meta_agent_schemas import AgentBlueprint, DeployRequest, SingleAgentResponse
from database import get_db_connection

load_dotenv()

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/meta-agent",
    tags=["Meta-Agent"]
)

NETWORK_SYSTEM_PROMPT = (
    "You are the Master Builder LLM for a No-Code Agent-Builder Platform. "
    "Your job is to analyze the client's prompt and output a structured JSON blueprint "
    "detailing the sub-agents, tools, and knowledge bases required to build their desired agent network. "
    "Ensure the output strictly follows the schema. "
    "Based on the client's use-case, generate strict Markdown formatting rules for each specific agent in output_format_instructions. "
    "For example, if it's an e-commerce agent, instruct it to output product images ![alt](url) and links [text](url)."
)

SINGLE_SYSTEM_PROMPT = (
    "You are an expert AI Agent Configurator. "
    "Your job is to analyze the client's request and output a structured JSON configuring a single AI Agent. "
    "Generate a catchy name, a clear description, a very detailed system prompt defining its persona and core rules, "
    "and strict formatting instructions for how it should output responses."
)


async def _generate_with_gemini(prompt: str, response_schema, system_instruction: str):
    """Try Gemini up to 3 times on 503, raising the last exception on failure."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not configured")

    client = genai.Client(api_key=api_key)
    last_exc = None
    for attempt in range(1, 4):
        try:
            logger.info(f"Gemini attempt {attempt}/3")
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    system_instruction=system_instruction,
                    temperature=0.2,
                ),
            )
            return response.text
        except Exception as e:
            last_exc = e
            error_str = str(e)
            if "503" in error_str or "UNAVAILABLE" in error_str:
                logger.warning(f"Gemini 503 on attempt {attempt}: {e}")
                if attempt < 3:
                    await asyncio.sleep(1.5 * attempt)
                    continue
            raise  # non-503 errors → bubble up immediately
    raise last_exc


async def _generate_with_groq(prompt: str, response_schema_class, system_instruction: str):
    """Fallback to Groq llama model with JSON mode."""
    import httpx

    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        raise ValueError("GROQ_API_KEY not configured")

    schema_json = json.dumps(response_schema_class.model_json_schema(), indent=2)
    full_system = (
        f"{system_instruction}\n\n"
        f"You MUST respond with ONLY valid JSON that exactly matches this schema:\n{schema_json}"
    )

    logger.info("Falling back to Groq llama-3.3-70b-versatile")
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": full_system},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"}
            }
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


class GenerateBlueprintRequest(BaseModel):
    prompt: str

@router.post("/generate", response_model=AgentBlueprint)
async def generate_blueprint(req: GenerateBlueprintRequest):
    raw_json = None
    provider_used = "gemini"
    try:
        raw_json = await _generate_with_gemini(req.prompt, AgentBlueprint, NETWORK_SYSTEM_PROMPT)
    except Exception as gemini_exc:
        logger.warning(f"Gemini failed after retries: {gemini_exc}. Switching to Groq.")
        provider_used = "groq"
        try:
            raw_json = await _generate_with_groq(req.prompt, AgentBlueprint, NETWORK_SYSTEM_PROMPT)
        except Exception as groq_exc:
            logger.error(f"Groq also failed: {groq_exc}")
            raise HTTPException(status_code=500, detail=f"All providers failed. Gemini: {gemini_exc}. Groq: {groq_exc}")

    try:
        logger.info(f"Blueprint generated via {provider_used}")
        return AgentBlueprint.model_validate_json(raw_json)
    except Exception as e:
        logger.error(f"Failed to parse blueprint JSON from {provider_used}: {e}\nRaw: {raw_json[:500]}")
        raise HTTPException(status_code=500, detail=f"Failed to parse blueprint from {provider_used}")



@router.post("/generate-single", response_model=SingleAgentResponse)
async def generate_single_agent(req: GenerateBlueprintRequest):
    raw_json = None
    provider_used = "gemini"
    try:
        raw_json = await _generate_with_gemini(req.prompt, SingleAgentResponse, SINGLE_SYSTEM_PROMPT)
    except Exception as gemini_exc:
        logger.warning(f"Gemini failed after retries (single): {gemini_exc}. Switching to Groq.")
        provider_used = "groq"
        try:
            raw_json = await _generate_with_groq(req.prompt, SingleAgentResponse, SINGLE_SYSTEM_PROMPT)
        except Exception as groq_exc:
            logger.error(f"Groq also failed (single): {groq_exc}")
            raise HTTPException(status_code=500, detail=f"All providers failed. Gemini: {gemini_exc}. Groq: {groq_exc}")

    try:
        logger.info(f"Single agent generated via {provider_used}")
        return SingleAgentResponse.model_validate_json(raw_json)
    except Exception as e:
        logger.error(f"Failed to parse single agent JSON from {provider_used}: {e}\nRaw: {raw_json[:500]}")
        raise HTTPException(status_code=500, detail=f"Failed to parse single agent from {provider_used}")

@router.post("/deploy")
async def deploy_agent(req: DeployRequest):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Insert into agent_projects
        cursor.execute(
            """
            INSERT INTO agent_projects (workspace_id, name, description, status, blueprint_json)
            VALUES (%s, %s, %s, 'deployed', %s)
            RETURNING id;
            """,
            (req.workspace_id, req.blueprint.project_name, req.blueprint.description, req.blueprint.model_dump_json())
        )
        project_id = cursor.fetchone()[0]

        # 2. Insert into documents (formerly knowledge_bases)
        enabled_kb = req.config_data.get("enabled_knowledge", {})
        for kb in req.blueprint.required_knowledge:
            if enabled_kb.get(kb.id):
                cursor.execute(
                    """
                    INSERT INTO documents (project_id, blueprint_knowledge_id, filename, type, source_uri, status)
                    VALUES (%s, %s, %s, %s, %s, 'pending')
                    """,
                    (project_id, kb.id, kb.name, kb.type, "")
                )

        # 3. Insert into agent_tools
        enabled_tools = req.config_data.get("enabled_tools", {})
        tools_config = req.config_data.get("tools", {})
        for tool in req.blueprint.required_tools:
            tool_config_data = tools_config.get(tool.id, {})
            # Store the enabled state inside the config so we know if it was skipped
            tool_config_data["is_enabled"] = bool(enabled_tools.get(tool.id))
            # Pre-fill empty fields for query format and headers
            if "query_format" not in tool_config_data:
                tool_config_data["query_format"] = "{}"
            if "headers" not in tool_config_data:
                tool_config_data["headers"] = "{}"
                
            cursor.execute(
                """
                INSERT INTO agent_tools (project_id, workspace_id, blueprint_tool_id, name, config)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (project_id, req.workspace_id, tool.id, tool.name, json.dumps(tool_config_data))
            )

        # 4. Insert Sub-Agents into the main 'agents' table
        # We need to do this in two passes to handle parent_agent_id linking properly
        # First pass: Insert all agents and keep a map of blueprint_id -> real_uuid
        agent_id_map = {}
        for sub_agent in req.blueprint.sub_agents:
            cursor.execute(
                """
                INSERT INTO agents (name, description, system_prompt, output_format, user_id, workspace_id, project_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    sub_agent.role, 
                    sub_agent.goal, 
                    sub_agent.backstory,
                    sub_agent.output_format_instructions,
                    req.user_id, 
                    req.workspace_id, 
                    project_id
                )
            )
            real_uuid = cursor.fetchone()[0]
            agent_id_map[sub_agent.id] = real_uuid

        # Second pass: Update parent_agent_id
        for sub_agent in req.blueprint.sub_agents:
            if getattr(sub_agent, 'parent_agent_id', None) and sub_agent.parent_agent_id in agent_id_map:
                real_uuid = agent_id_map[sub_agent.id]
                parent_real_uuid = agent_id_map[sub_agent.parent_agent_id]
                cursor.execute(
                    """
                    UPDATE agents SET parent_agent_id = %s WHERE id = %s
                    """,
                    (parent_real_uuid, real_uuid)
                )

        # 5. Fetch the inserted tools to get their real UUIDs
        cursor.execute("SELECT blueprint_tool_id, id FROM agent_tools WHERE project_id = %s", (project_id,))
        tool_id_map = {row[0]: row[1] for row in cursor.fetchall()}

        conn.commit()
        return {
            "status": "success", 
            "project_id": project_id, 
            "agent_id_map": agent_id_map,
            "tool_id_map": tool_id_map
        }
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error deploying agent network: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
