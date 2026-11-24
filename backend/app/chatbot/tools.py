<<<<<<< HEAD
import io
import json
import logging
=======

import ast
import io
import json
import logging
import math
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
import os
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .attachments import (
    get_attachment,
    get_attachment_bytes,
    select_relevant_chunks,
)
from .convert import (
    run_chatbot_conversion,
    save_converted_document_for_user,
    SUPPORTED_CONVERSIONS,
)

logger = logging.getLogger(__name__)

<<<<<<< HEAD
# OpenAI-compatible tool definitions for OpenRouter
=======

# ============================================================
# SAFE CALCULATOR
# ============================================================

CALCULATOR_FUNCTIONS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
}

CALCULATOR_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
}


def safe_calculate(expression: str) -> float | int:
    """
    Safely evaluates basic mathematical expressions using AST.
    Arbitrary Python code is never executed.
    """

    if not isinstance(expression, str):
        raise ValueError("Expression must be text.")

    expression = expression.strip()

    if not expression or len(expression) > 256:
        raise ValueError("Expression must contain 1-256 characters.")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Invalid mathematical expression.") from exc

    if len(list(ast.walk(tree))) > 50:
        raise ValueError("Expression is too complex.")

    def evaluate(node):

        if isinstance(node, ast.Expression):
            return evaluate(node.body)

        # Numeric constants only
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                raise ValueError("Boolean values are not allowed.")

            if isinstance(node.value, (int, float)):
                if not math.isfinite(node.value):
                    raise ValueError("Invalid numeric value.")
                return node.value

            raise ValueError("Only numeric values are allowed.")

        # Mathematical constants
        if isinstance(node, ast.Name):
            if node.id in CALCULATOR_CONSTANTS:
                return CALCULATOR_CONSTANTS[node.id]

            raise ValueError(f"Unknown constant: {node.id}")

        # Unary operations
        if isinstance(node, ast.UnaryOp):
            value = evaluate(node.operand)

            if isinstance(node.op, ast.UAdd):
                return value

            if isinstance(node.op, ast.USub):
                return -value

            raise ValueError("Unsupported unary operation.")

        # Binary operations
        if isinstance(node, ast.BinOp):
            left = evaluate(node.left)
            right = evaluate(node.right)

            if isinstance(node.op, ast.Add):
                result = left + right

            elif isinstance(node.op, ast.Sub):
                result = left - right

            elif isinstance(node.op, ast.Mult):
                result = left * right

            elif isinstance(node.op, ast.Div):
                if right == 0:
                    raise ValueError("Division by zero is not allowed.")
                result = left / right

            elif isinstance(node.op, ast.FloorDiv):
                if right == 0:
                    raise ValueError("Division by zero is not allowed.")
                result = left // right

            elif isinstance(node.op, ast.Mod):
                if right == 0:
                    raise ValueError("Division by zero is not allowed.")
                result = left % right

            elif isinstance(node.op, ast.Pow):
                if abs(right) > 100:
                    raise ValueError("Exponent is too large.")

                if abs(left) > 1e100:
                    raise ValueError("Base is too large.")

                result = left ** right

            else:
                raise ValueError("Unsupported mathematical operation.")

            if not isinstance(result, (int, float)):
                raise ValueError("Invalid calculation result.")

            if not math.isfinite(result) or abs(result) > 1e100:
                raise ValueError("Calculation result is out of range.")

            return result

        # Approved mathematical functions only
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Unsupported function call.")

            function_name = node.func.id

            if function_name not in CALCULATOR_FUNCTIONS:
                raise ValueError(
                    f"Function '{function_name}' is not supported."
                )

            if node.keywords:
                raise ValueError("Keyword arguments are not supported.")

            if len(node.args) > 10:
                raise ValueError("Too many function arguments.")

            arguments = [evaluate(arg) for arg in node.args]

            result = CALCULATOR_FUNCTIONS[function_name](*arguments)

            if not isinstance(result, (int, float)):
                raise ValueError("Invalid function result.")

            if not math.isfinite(result) or abs(result) > 1e100:
                raise ValueError("Calculation result is out of range.")

            return result

        raise ValueError(
            f"Unsupported expression element: {type(node).__name__}"
        )

    try:
        return evaluate(tree)
    except (ArithmeticError, OverflowError) as exc:
        raise ValueError(f"Calculation error: {exc}") from exc


def tool_calculator(expression: str) -> dict[str, Any]:
    """Execute a safe mathematical calculation."""

    result = safe_calculate(expression)

    return {
        "status": "success",
        "expression": expression,
        "result": result,
        "formatted_result": str(result),
    }


# ============================================================
# CHATBOT TOOL DEFINITIONS
# ============================================================

>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
CHATBOT_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "convert_document",
<<<<<<< HEAD
            "description": "Convert an attached document to a different file format (e.g. DOCX to PDF, PDF to DOCX, TXT to PDF). Returns download details for the converted file.",
=======
            "description": "Convert an attached document to a different file format. Returns download details.",
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
            "parameters": {
                "type": "object",
                "properties": {
                    "attachment_id": {
                        "type": "string",
<<<<<<< HEAD
                        "description": "The unique ID of the attachment to convert.",
=======
                        "description": "Unique attachment ID.",
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
                    },
                    "target_format": {
                        "type": "string",
                        "enum": ["pdf", "docx", "txt"],
<<<<<<< HEAD
                        "description": "The desired target format: 'pdf', 'docx', or 'txt'.",
=======
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
                    },
                },
                "required": ["attachment_id", "target_format"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
<<<<<<< HEAD
            "description": "Read and return the extracted plain text content of an attached document.",
=======
            "description": "Read the extracted text content of an attached document.",
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
            "parameters": {
                "type": "object",
                "properties": {
                    "attachment_id": {
                        "type": "string",
<<<<<<< HEAD
                        "description": "The unique ID of the attachment to read.",
=======
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
                    },
                },
                "required": ["attachment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_document_info",
<<<<<<< HEAD
            "description": "Get metadata and statistics about an attached document (filename, size, character count, type, scanned status).",
=======
            "description": "Get metadata and statistics about an attached document.",
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
            "parameters": {
                "type": "object",
                "properties": {
                    "attachment_id": {
                        "type": "string",
<<<<<<< HEAD
                        "description": "The unique ID of the attachment.",
=======
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
                    },
                },
                "required": ["attachment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_document",
<<<<<<< HEAD
            "description": "Summarize an attached document using a specific style: 'concise', 'detailed', or 'bullet_points'.",
=======
            "description": "Summarize an attached document using a specific style.",
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
            "parameters": {
                "type": "object",
                "properties": {
                    "attachment_id": {
                        "type": "string",
<<<<<<< HEAD
                        "description": "The unique ID of the attachment to summarize.",
=======
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
                    },
                    "style": {
                        "type": "string",
                        "enum": ["concise", "detailed", "bullet_points"],
<<<<<<< HEAD
                        "description": "The summary style desired.",
=======
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
                    },
                },
                "required": ["attachment_id"],
            },
        },
    },
<<<<<<< HEAD
]


=======
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": (
                "Calculate mathematical expressions. Supports addition, "
                "subtraction, multiplication, division, powers, brackets, "
                "square roots, trigonometric functions, logarithms, "
                "and basic mathematical functions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": (
                            "Mathematical expression, for example 125 * 8."
                        ),
                    },
                },
                "required": ["expression"],
            },
        },
    },
]


# ============================================================
# EXISTING DOCUMENT TOOLS
# ============================================================

>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
def tool_convert_document(
    attachment_id: str,
    target_format: str,
    owner_id: int,
    db: Session,
) -> dict[str, Any]:
<<<<<<< HEAD
    """
    Executes real server-side document conversion.
    Returns structured artifact data with download URL.
    """
    try:
        content, src_filename = get_attachment_bytes(attachment_id, owner_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(404, f"Attachment could not be accessed: {e}") from e

    src_ext = src_filename.rsplit(".", 1)[-1].lower() if "." in src_filename else ""
    tgt = target_format.lower().strip()
=======

    try:
        content, src_filename = get_attachment_bytes(
            attachment_id, owner_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            404, f"Attachment could not be accessed: {e}"
        ) from e

    src_ext = (
        src_filename.rsplit(".", 1)[-1].lower()
        if "." in src_filename else ""
    )

    tgt = target_format.lower().strip()

>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
    if tgt == "text":
        tgt = "txt"

    pair = (src_ext, tgt)
<<<<<<< HEAD
    if pair not in SUPPORTED_CONVERSIONS and not (src_ext in {"jpg", "jpeg", "png", "webp"} and tgt == "pdf"):
        raise HTTPException(
            415,
            f"Converting from .{src_ext} to {tgt.upper()} is not currently supported (Coming soon).",
        )

    try:
        out_bytes, media_type, out_filename = run_chatbot_conversion(content, src_filename, tgt)
        saved_doc = save_converted_document_for_user(out_bytes, out_filename, media_type, owner_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Conversion engine error")
        raise HTTPException(500, f"Conversion engine failed: {str(e)}") from e
=======

    if pair not in SUPPORTED_CONVERSIONS and not (
        src_ext in {"jpg", "jpeg", "png", "webp"} and tgt == "pdf"
    ):
        raise HTTPException(
            415,
            f"Converting from .{src_ext} to {tgt.upper()} "
            "is not currently supported (Coming soon).",
        )

    try:
        out_bytes, media_type, out_filename = run_chatbot_conversion(
            content, src_filename, tgt
        )

        saved_doc = save_converted_document_for_user(
            out_bytes, out_filename, media_type, owner_id, db
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("Conversion engine error")
        raise HTTPException(
            500, f"Conversion engine failed: {str(e)}"
        ) from e
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5

    return {
        "status": "success",
        "artifact": {
            "type": "download",
            "document_id": saved_doc.id,
            "filename": saved_doc.original_name,
            "size": saved_doc.size,
            "content_type": saved_doc.content_type,
            "url": f"/api/documents/{saved_doc.id}/download",
        },
<<<<<<< HEAD
        "message": f"Successfully converted {src_filename} to {tgt.upper()}.",
    }


def tool_read_document(attachment_id: str, owner_id: int) -> dict[str, Any]:
    att = get_attachment(attachment_id, owner_id)
    text = att.get("extracted_text", "")
=======
        "message": (
            f"Successfully converted {src_filename} to {tgt.upper()}."
        ),
    }


def tool_read_document(
    attachment_id: str,
    owner_id: int,
) -> dict[str, Any]:

    att = get_attachment(attachment_id, owner_id)
    text = att.get("extracted_text", "")

>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
    return {
        "filename": att.get("filename"),
        "char_count": len(text),
        "is_scanned": att.get("is_scanned", False),
        "content": text[:15000],
    }


<<<<<<< HEAD
def tool_get_document_info(attachment_id: str, owner_id: int) -> dict[str, Any]:
    att = get_attachment(attachment_id, owner_id)
    text = att.get("extracted_text", "")
    words = len(text.split()) if text else 0
=======
def tool_get_document_info(
    attachment_id: str,
    owner_id: int,
) -> dict[str, Any]:

    att = get_attachment(attachment_id, owner_id)
    text = att.get("extracted_text", "")
    words = len(text.split()) if text else 0

>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
    return {
        "id": att["id"],
        "filename": att.get("filename"),
        "size": att.get("size", 0),
        "extension": att.get("extension"),
        "word_count": words,
        "char_count": len(text),
        "is_image": att.get("is_image", False),
        "is_scanned": att.get("is_scanned", False),
    }


def tool_summarize_document(
    attachment_id: str,
    style: str,
    owner_id: int,
) -> dict[str, Any]:
<<<<<<< HEAD
    att = get_attachment(attachment_id, owner_id)
    text = att.get("extracted_text", "")
    if not text.strip():
        if att.get("is_scanned"):
            return {"error": "OCR not available: this document appears to be a scanned image."}
        return {"error": "Document contains no readable text to summarize."}

    summary_context = select_relevant_chunks(text, "overview summary key points", budget=12000)
=======

    att = get_attachment(attachment_id, owner_id)
    text = att.get("extracted_text", "")

    if not text.strip():
        if att.get("is_scanned"):
            return {
                "error": (
                    "OCR not available: this document appears "
                    "to be a scanned image."
                )
            }

        return {
            "error": "Document contains no readable text to summarize."
        }

    summary_context = select_relevant_chunks(
        text,
        "overview summary key points",
        budget=12000,
    )

>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
    return {
        "filename": att.get("filename"),
        "style": style,
        "document_excerpt": summary_context,
    }


<<<<<<< HEAD
=======
# ============================================================
# CENTRAL TOOL EXECUTOR
# ============================================================

>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
def execute_tool_call(
    tool_name: str,
    arguments: dict[str, Any],
    owner_id: int,
    db: Session,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
<<<<<<< HEAD
    """
    Executes a registered tool. Returns (result_dict, optional_artifact).
    """
    logger.info("Executing chatbot tool '%s' with args %s", tool_name, arguments)
    if tool_name == "convert_document":
        att_id = arguments.get("attachment_id", "")
        tgt = arguments.get("target_format", "pdf")
        res = tool_convert_document(att_id, tgt, owner_id, db)
        return res, res.get("artifact")

    elif tool_name == "read_document":
        att_id = arguments.get("attachment_id", "")
        res = tool_read_document(att_id, owner_id)
        return res, None

    elif tool_name == "get_document_info":
        att_id = arguments.get("attachment_id", "")
        res = tool_get_document_info(att_id, owner_id)
        return res, None

    elif tool_name == "summarize_document":
        att_id = arguments.get("attachment_id", "")
        style = arguments.get("style", "concise")
        res = tool_summarize_document(att_id, style, owner_id)
        return res, None

    raise HTTPException(400, f"Unknown tool: {tool_name}")


def detect_fastpath_intent(message: str) -> tuple[str, str | None] | None:
    """
    Deterministic fast-path detection:
    Returns (action_type, parameter) or None.
    e.g. ('convert', 'pdf'), ('summarize', None), ('key_points', None)
    """
=======

    """
    Executes a registered tool.
    Returns (result_dict, optional_artifact).
    """

    logger.info(
        "Executing chatbot tool '%s' with args %s",
        tool_name,
        arguments,
    )

    if tool_name == "convert_document":

        att_id = arguments.get("attachment_id", "")
        tgt = arguments.get("target_format", "pdf")

        res = tool_convert_document(
            att_id, tgt, owner_id, db
        )

        return res, res.get("artifact")

    elif tool_name == "read_document":

        att_id = arguments.get("attachment_id", "")
        res = tool_read_document(att_id, owner_id)

        return res, None

    elif tool_name == "get_document_info":

        att_id = arguments.get("attachment_id", "")
        res = tool_get_document_info(att_id, owner_id)

        return res, None

    elif tool_name == "summarize_document":

        att_id = arguments.get("attachment_id", "")
        style = arguments.get("style", "concise")

        res = tool_summarize_document(
            att_id, style, owner_id
        )

        return res, None

    elif tool_name == "calculator":

        expression = arguments.get("expression", "")

        try:
            res = tool_calculator(expression)
            return res, None

        except (ValueError, TypeError) as exc:
            return {
                "status": "error",
                "error": str(exc),
            }, None

    raise HTTPException(
        400,
        f"Unknown tool: {tool_name}",
    )


# ============================================================
# EXISTING FAST-PATH INTENT DETECTION
# ============================================================

def detect_fastpath_intent(
    message: str,
) -> tuple[str, str | None] | None:

    """
    Deterministic fast-path detection.
    Returns (action_type, parameter) or None.
    """

>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
    msg = message.lower().strip()

    # 1. Conversion intents
    conv_match = re.search(
<<<<<<< HEAD
        r"(?:convert|change|transform|export|save)(?:\s+this)?(?:\s+document|\s+file|\s+it)?\s+(?:in)?to\s+(pdf|docx|txt|text|doc)",
        msg,
    )
    if conv_match:
        tgt = conv_match.group(1).lower()
        return ("convert", "txt" if tgt == "text" else ("docx" if tgt == "doc" else tgt))

    if re.search(r"\bconvert\s+(?:to\s+)?(pdf|docx|txt)\b", msg):
        target = re.search(r"\bconvert\s+(?:to\s+)?(pdf|docx|txt)\b", msg).group(1)
        return ("convert", target)

    if re.search(r"\b(?:make|give)(?:\s+me)?\s+(?:this\s+)?(?:a\s+)?(pdf|docx|txt)\b", msg):
        target = re.search(r"\b(?:make|give)(?:\s+me)?\s+(?:this\s+)?(?:a\s+)?(pdf|docx|txt)\b", msg).group(1)
        return ("convert", target)

    # 2. Summarize intents
    if re.search(r"^(?:summarize|summary|summarise)(?:\s+this|\s+the)?(?:\s+document|\s+file)?$", msg):
        return ("summarize", "concise")

    # 3. Key points intents
    if re.search(r"^(?:extract\s+)?key\s+points(?:\s+of\s+this)?(?:\s+document|\s+file)?$", msg):
        return ("key_points", None)

    # 4. Explain simply intents
    if re.search(r"^explain\s+(?:this\s+)?simply$", msg):
=======
        r"(?:convert|change|transform|export|save)"
        r"(?:\s+this)?(?:\s+document|\s+file|\s+it)?"
        r"\s+(?:in)?to\s+(pdf|docx|txt|text|doc)",
        msg,
    )

    if conv_match:
        tgt = conv_match.group(1).lower()

        return (
            "convert",
            "txt" if tgt == "text" else (
                "docx" if tgt == "doc" else tgt
            ),
        )

    match = re.search(
        r"\bconvert\s+(?:to\s+)?(pdf|docx|txt)\b",
        msg,
    )

    if match:
        return ("convert", match.group(1))

    match = re.search(
        r"\b(?:make|give)(?:\s+me)?\s+(?:this\s+)?"
        r"(?:a\s+)?(pdf|docx|txt)\b",
        msg,
    )

    if match:
        return ("convert", match.group(1))

    # 2. Summarize intents
    if re.search(
        r"^(?:summarize|summary|summarise)"
        r"(?:\s+this|\s+the)?(?:\s+document|\s+file)?$",
        msg,
    ):
        return ("summarize", "concise")

    # 3. Key points intents
    if re.search(
        r"^(?:extract\s+)?key\s+points"
        r"(?:\s+of\s+this)?(?:\s+document|\s+file)?$",
        msg,
    ):
        return ("key_points", None)

    # 4. Explain simply intents
    if re.search(
        r"^explain\s+(?:this\s+)?simply$",
        msg,
    ):
>>>>>>> b7386e9dd9cf8207da18e0834c953df908a095c5
        return ("explain_simply", None)

    return None
