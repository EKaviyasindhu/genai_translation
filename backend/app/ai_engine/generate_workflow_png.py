import os
from graphviz import Digraph

def generate_workflow_png():

    # Output folder
    base_dir = os.path.dirname(os.path.abspath(__file__))   # backend/app/ai_engine
    output_dir = os.path.join(base_dir, "..", "static", "graph")
    output_dir = os.path.abspath(output_dir)
    
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "langgraph_workflow")

    dot = Digraph(format="png")
    dot.attr(rankdir='TB', fontsize='10', bgcolor="white")

    # ----------- NODES -----------
    dot.node("A", "Start", style="filled", fillcolor="#D5F5E3")  
    dot.node("B", "Input Type?", style="filled", fillcolor="#FCF3CF")

    dot.node("T", "Text Input", style="filled", fillcolor="#EBF5FB")
    dot.node("AU", "Audio Upload", style="filled", fillcolor="#EBF5FB")
    dot.node("IM", "Image Upload", style="filled", fillcolor="#EBF5FB")
    dot.node("VI", "Video Upload", style="filled", fillcolor="#EBF5FB")
    dot.node("DO", "Document Upload", style="filled", fillcolor="#EBF5FB")

    dot.node("MOD", "Moderation Check", style="filled", fillcolor="#FAD7A0")
    dot.node("MODF", "Moderation Fail", style="filled", fillcolor="#F5B7B1")

    dot.node("D1", "Detect Language", style="filled", fillcolor="#D6EAF8")
    dot.node("TR1", "Translate (if enabled)", style="filled", fillcolor="#D6EAF8")
    dot.node("OP", "Output Preference\n(Audio/Text/Both)", style="filled", fillcolor="#E8DAEF")

    dot.node("ASR", "ASR (Speech-to-Text)", style="filled", fillcolor="#FDEDEC")
    dot.node("OCR", "OCR (Extract Text)", style="filled", fillcolor="#FDEDEC")
    dot.node("VID", "Extract Audio (from Video)", style="filled", fillcolor="#FDEDEC")
    dot.node("DOC", "Extract Text (Document)", style="filled", fillcolor="#FDEDEC")
    dot.node("SUM", "Summarize (Long Docs Only)", style="filled", fillcolor="#FDEDEC")

    dot.node("TTS", "Generate TTS (if needed)", style="filled", fillcolor="#D4EFDF")
    dot.node("END", "Save JSON + Audio + Text\nReturn Response", style="filled", fillcolor="#ABEBC6")

    # ----------- EDGES -----------
    dot.edge("A", "B")

    dot.edge("B", "T", label="Text")
    dot.edge("B", "AU", label="Audio")
    dot.edge("B", "IM", label="Image")
    dot.edge("B", "VI", label="Video")
    dot.edge("B", "DO", label="Document")

    # TEXT
    dot.edge("T", "MOD")

    # AUDIO
    dot.edge("AU", "ASR")
    dot.edge("ASR", "MOD")

    # IMAGE
    dot.edge("IM", "OCR")
    dot.edge("OCR", "MOD")

    # VIDEO
    dot.edge("VI", "VID")
    dot.edge("VID", "ASR")
    dot.edge("ASR", "MOD")

    # DOCUMENT
    dot.edge("DO", "DOC")
    dot.edge("DOC", "MOD")
    dot.edge("DOC", "SUM", label="Long Docs Only", style="dashed")
    dot.edge("SUM", "MOD")

    # Moderation outcomes
    dot.edge("MOD", "MODF", label="Rejected", color="red", fontcolor="red")
    dot.edge("MOD", "D1", label="Approved")

    # Common path
    dot.edge("D1", "TR1")
    dot.edge("TR1", "OP")
    dot.edge("OP", "TTS", label="Audio / Both")
    dot.edge("OP", "END", label="Text")
    dot.edge("TTS", "END")

    # ----------- SAVE PNG -----------
    dot.render(output_path, cleanup=True)

    print(f"Workflow PNG generated at: {output_path}.png")

if __name__ == "__main__":
    generate_workflow_png()
