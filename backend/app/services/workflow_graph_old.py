def get_dynamic_workflow():
    return """
flowchart TD
    A[Request Received] --> B{kind?}

    B -->|text| C1[handle_text]
    B -->|audio| C2[handle_audio]
    B -->|document| C3[handle_document]
    B -->|image| C4[handle_image]
    B -->|video| C5[handle_video]

    C1 --> D[JSON Save + MongoDB]
    C2 --> D
    C3 --> D
    C4 --> D
    C5 --> D

    D --> E[Return Final Response]
    """
