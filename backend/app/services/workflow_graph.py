def get_dynamic_workflow():
    return """
flowchart TD
    A[Start] --> B{Input Type?}

    B -->|Text| C1[User Text]
    B -->|Audio| C2[Uploaded Audio]
    B -->|Image| C3[Uploaded Image]
    B -->|Video| C4[Uploaded Video]
    B -->|Document| C5[Uploaded Document]

    %% TEXT WORKFLOW
    C1 --> T1[Detect Language]
    T1 --> T2{Translate?}
    T2 -->|Yes| T3[Translate Text]
    T2 -->|No| T4[Skip Translation]
    T3 --> T5{Output Preference}
    T5 -->|Text| T6[Return Translated Text]
    T5 -->|Audio| T7[Generate TTS]
    T5 -->|Both| T8[Text + TTS]

    %% AUDIO WORKFLOW
    C2 --> A1[Speech-to-Text (ASR)]
    A1 --> A2[Detect Language]
    A2 --> A3[Translate Text]
    A3 --> A4{Output Preference}
    A4 -->|Text| A5[Return Translated Text]
    A4 -->|Audio| A6[Generate TTS]
    A4 -->|Both| A7[Text + TTS]

    %% IMAGE WORKFLOW
    C3 --> I1[OCR → Extract Text]
    I1 --> I2[Detect Language]
    I2 --> I3[Translate Text]
    I3 --> I4{Output Preference}
    I4 -->|Text| I5[Return Translated Text]
    I4 -->|Audio| I6[Generate TTS]
    I4 -->|Both| I7[Text + TTS]

    %% VIDEO WORKFLOW
    C4 --> V1[Extract Audio]
    V1 --> V2[ASR → Transcribed Text]
    V2 --> V3[Detect Language]
    V3 --> V4[Translate Text]
    V4 --> V5{Output Preference}
    V5 -->|Text| V6[Return Text]
    V5 -->|Audio| V7[Generate TTS]
    V5 -->|Both| V8[Text + TTS]

    %% DOCUMENT WORKFLOW
    C5 --> D1[Extract Text]
    D1 --> D2[Detect Language]
    
    %% Branch for long documents (optional)
    D2 --> D3{Long Document?}
    D3 -->|Yes| D4[Generate Summary]
    D3 -->|No| D5[Use Full Text]

    D4 --> D6[Translate Summary]
    D5 --> D7[Translate Full Text]

    D6 --> D8{Output Preference}
    D7 --> D8{Output Preference}

    D8 -->|Text| D9[Return Text / Summary]
    D8 -->|Audio| D10[Generate TTS]
    D8 -->|Both| D11[Text + TTS]

    %% Final Save and Response
    T6 --> Z[Save as JSON + Audio + Text → Return Response]
    T7 --> Z
    T8 --> Z

    A5 --> Z
    A6 --> Z
    A7 --> Z

    I5 --> Z
    I6 --> Z
    I7 --> Z

    V6 --> Z
    V7 --> Z
    V8 --> Z

    D9 --> Z
    D10 --> Z
    D11 --> Z
"""