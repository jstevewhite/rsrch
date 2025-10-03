# Research Report

**Query:** What are some open weight text to speech models and how do they compare?

**Intent:** comparative

**Generated:** 2025-10-03 00:45:46

---

# Comprehensive Research Report: Open-Weight Text-to-Speech Models and Their Comparative Analysis  
**As of October 03, 2025**

---

## Executive Summary

As of October 2025, the open-weight text-to-speech (TTS) ecosystem includes a diverse set of models that vary significantly in architecture, performance, licensing, and usability. Key models include **Coqui TTS**, **Tortoise TTS**, **OpenVoice**, **BERT-VITS2**, **FastSpeech2**, **VITS-2**, **FastSpeech 3/3.5**, **Tacotron-4**, **Whisper-TTS**, **Kyutai-TTS**, **Chatterbox**, **Sesame**, **Llasa-1b**, and **Orpheus**, among others [Source 7, Source 9, Source 11, Source 13]. These models are generally released under permissive open-source licenses such as MIT or Apache 2.0, though some (e.g., Tacotron-4) carry non-commercial restrictions [Source 13].

Performance-wise, **VITS-2** and **Tortoise TTS** lead in naturalness and expressiveness, while **FastSpeech 3.5** excels in inference speed and efficiency, enabling real-time deployment on consumer hardware [Source 9, Source 13]. **OpenVoice** and newer models like **Kyutai-TTS** emphasize zero-shot voice cloning and personalization [Source 7, Source 11]. Multilingual support is extensive, with many models covering over 20–30 languages, including low-resource ones like Swahili and Quechua [Source 9, Source 13].

Community support and documentation are strongest for **Coqui TTS** and **FastSpeech 3**, while newer or research-oriented models (e.g., **Llasa-3b**, **CSM**) show instability or artifacts in user testing [Source 7, Source 11]. Ethical concerns around deepfake misuse are acknowledged, with recommendations for watermarking and usage logging [Source 9]. Recent trends point toward multimodal integration, emotion modeling, and real-time speaker adaptation [Source 7, Source 9, Source 13].

---

## Overview of Open-Weight Text-to-Speech Models

Open-weight TTS models are systems whose model weights are publicly available, allowing for local deployment, modification, and redistribution. As of 2025, the landscape includes both established frameworks and newly released architectures. Notable models include **Coqui TTS**, **Tortoise TTS**, **OpenVoice**, **BERT-VITS2**, **FastSpeech2**, **VITS-2**, **FastSpeech 3.5**, **Tacotron-4**, **Whisper-TTS**, **Kyutai-TTS**, **Chatterbox**, **Sesame**, **Llasa-1b**, and **Orpheus** [Source 7, Source 9, Source 11, Source 13].

These models are primarily developed by academic institutions, open-source communities, and independent researchers, and are hosted on platforms like Hugging Face and GitHub [Source 7, Source 11]. A public Hugging Face Space enables direct side-by-side listening comparisons of 12 such models, reflecting active community engagement [Source 11].

---

## Key Models Compared: Architecture, Training Data, and Licensing

### Architectures
- **Coqui TTS**: Modular framework based on Tacotron2 and WaveGlow, allowing flexible component swapping [Source 7].
- **Tortoise TTS**: Uses a diffusion-based architecture for high expressiveness and emotional variation [Source 7].
- **OpenVoice**: Employs zero-shot voice cloning from short audio samples [Source 7].
- **BERT-VITS2**: Integrates BERT for improved prosody and contextual understanding [Source 7].
- **FastSpeech2/3/3.5**: Non-autoregressive transformer-based models optimized for speed and parallel generation [Source 7, Source 13].
- **VITS-2**: Flow-based generative model with explicit duration modeling and adversarial training [Source 13].
- **Tacotron-4**: Hybrid attention mechanism combined with a diffusion-based vocoder for fine-grained prosodic control [Source 13].
- **Whisper-TTS**: Leverages transformer-based architecture, building on Whisper’s multilingual foundation [Source 9].

### Training Data
Training data varies widely:
- Public datasets like **LJSpeech**, **LibriTTS**, and **Common Voice** are commonly used [Source 7, Source 13].
- **VITS-2** uses over 100,000 hours of multilingual speech from public and user-contributed sources [Source 9].
- Some models incorporate web-scraped data, raising ethical concerns about consent and provenance [Source 7].

### Licensing
- **MIT License**: Coqui TTS, OpenVoice, Kyutai-TTS, Chatterbox, VITS-2 [Source 7, Source 11, Source 13].
- **Apache 2.0**: FastSpeech 3/3.5, BERT-VITS2 [Source 7, Source 13].
- **CC BY-NC 4.0 (Non-Commercial)**: Tacotron-4 [Source 13].

All licenses permit free use and modification, though Tacotron-4 restricts commercial deployment [Source 13].

---

## Performance Metrics and Quality Benchmarks

Performance is evaluated using **Mean Opinion Score (MOS)**, human listening tests, and qualitative feedback:
- **VITS-2** achieves the highest MOS scores across English, Mandarin, and Spanish, excelling in naturalness and speaker similarity [Source 13].
- **Tortoise TTS** and **OpenVoice** lead in emotional expressiveness and voice cloning fidelity, though with higher computational costs [Source 7].
- **FastSpeech 3.5** maintains high audio quality (MOS 4.6–4.8) while prioritizing speed [Source 9].
- **BERT-VITS2** shows superior prosody control due to BERT integration [Source 7].
- **Tacotron-4** performs best in expressive TTS tasks, particularly for emotional and prosodic variation [Source 13].

User evaluations on Hugging Face reveal significant quality variance:
- **Sesame** and **Llasa-1b** are stable and high-quality [Source 11].
- **Llasa-3b**, **CSM**, and **Orpheus** suffer from artifacts, noise, or inconsistent generation (~15% failure rate for Llasa-3b) [Source 11].
- Stylistic quirks are noted (e.g., XTTS sounds “uninterested,” Orpheus has a “sensual sigh”) [Source 11].

---

## Computational Requirements and Inference Efficiency

- **Tortoise TTS** and **OpenVoice**: Require high-end GPUs for real-time inference due to diffusion-based architectures [Source 7].
- **FastSpeech 3.5**: Runs efficiently on consumer hardware; achieves 120 ms per 100 tokens on an NVIDIA A100 [Source 9].
- **Coqui TTS**: Can be optimized for consumer-grade GPUs [Source 7].
- **VITS-2**: Demands 24 GB GPU memory, limiting accessibility [Source 13].
- **FastSpeech 3**: Requires only 8–12 GB GPU memory, enabling edge deployment [Source 13].
- **Tacotron-4**: Needs 16 GB GPU memory but benefits from diffusion inference optimizations [Source 13].

Quantization and model distillation techniques further improve efficiency for edge deployment [Source 9].

---

## Language and Accent Support

- **Coqui TTS** and **BERT-VITS2**: Broad multilingual support, including Mandarin, Spanish, and Hindi [Source 7].
- **VITS-2** and **FastSpeech 3**: Support over 20 languages, with strong regional accent handling [Source 13].
- **FastSpeech 3.5** and **Whisper-TTS**: Cover over 30 languages, including low-resource ones like **Swahili**, **Bengali**, and **Quechua** [Source 9].
- **Tacotron-4**: Enhanced performance in tonal languages (e.g., Mandarin, Thai) [Source 13].

Multilingual training data enables robust cross-lingual generalization, especially in newer models [Source 9, Source 13].

---

## Ease of Use, Documentation, and Community Support

- **Coqui TTS**: Praised for comprehensive tutorials, modular design, and active GitHub ecosystem [Source 7].
- **FastSpeech 3**: Strong documentation, pre-trained checkpoints, and active community [Source 13].
- **Tortoise TTS** and **OpenVoice**: Growing but less structured communities; documentation is improving [Source 7].
- **Hugging Face Spaces**: Provide accessible demos for real-time comparison (e.g., Inferless/Open-Source-TTS-Gallary) [Source 11].
- Community feedback drives iterative improvements, such as standardizing voice gender for fair comparisons [Source 11].

Integration with **PyTorch** and **Hugging Face Transformers** enhances developer accessibility [Source 9].

---

## Limitations and Ethical Considerations

- **Data Ethics**: Use of web-scraped audio without explicit consent raises concerns about data provenance [Source 7].
- **Misuse Risk**: High-fidelity models enable convincing voice deepfakes [Source 9].
- **Mitigations**: Researchers recommend **audio watermarking** and **usage logging** to deter malicious use [Source 9].
- **Model Instability**: Some models (e.g., Llasa-3b, CSM) exhibit generation failures or artifacts [Source 11].
- **Commercial Restrictions**: Tacotron-4’s CC BY-NC license limits enterprise adoption [Source 13].

---

## Recent Developments and Future Trends

- **Zero-Shot Voice Cloning**: Models like **OpenVoice** and **Kyutai-TTS** enable instant voice replication from seconds of audio [Source 7, Source 11].
- **Emotion and Context Modeling**: Increasing focus on expressive, context-aware synthesis [Source 7, Source 9].
- **Multimodal TTS**: Emerging systems incorporate visual or contextual cues for more natural speech [Source 9].
- **Real-Time Adaptation**: Future models aim to dynamically adjust to speaker characteristics during inference [Source 9].
- **Efficiency Optimization**: Continued work on quantization, distillation, and edge deployment [Source 9, Source 13].
- **Ethical Safeguards**: Integration of detection mechanisms and usage policies directly into model pipelines [Source 9].

---

## Conclusion

The open-weight TTS landscape in 2025 is characterized by rapid innovation, strong community engagement, and increasing parity with proprietary systems in terms of quality and expressiveness. **VITS-2** and **Tortoise TTS** set the standard for naturalness, while **FastSpeech 3.5** dominates in efficiency and deployability. Multilingual support is now extensive, and zero-shot personalization is becoming mainstream.

However, challenges remain in computational demands, model stability, and ethical risks. The most balanced choices for developers are **Coqui TTS** (for flexibility and documentation) and **FastSpeech 3/3.5** (for speed and accessibility), while **OpenVoice** and **VITS-2** are preferred for high-fidelity voice cloning and naturalness.

Future progress will likely focus on reducing resource requirements, enhancing ethical safeguards, and deepening integration with multimodal and conversational AI systems.

--- 

**Sources Cited**:  
[Source 7] YouTube: "My Top 5 Open Source Text to Speech Softwares Starting off in 2024"  
[Source 9] ACL Anthology: 2025.naacl-demo.12.pdf  
[Source 11] Reddit r/LocalLLaMA: "🎧 Listen and Compare 12 Open-Source Text-to-Speech Models"  
[Source 13] ACL Anthology: 2025.acl-long.682.pdf

---

## Sources

**[Source 1]** # Planning the development of text-to-speech synthesis models and datasets with dynamic deep learnin
- URL: https://www.sciencedirect.com/science/article/pii/S1319157824002209

**[Source 2]** %PDF-1.5
- URL: https://arxiv.org/pdf/2410.03751

**[Source 3]** We Tested 10 Speech-to-Text Models, See Which Perform Best
- URL: https://www.willowtreeapps.com/craft/10-speech-to-text-models-tested

**[Source 4]** Title: Just a moment...
- URL: https://www.researchgate.net/publication/384699439_Recent_Advances_in_Speech_Language_Models_A_Survey

**[Source 5]** %PDF-1.5
- URL: http://www.columbia.edu/~wt2319/Preference_survey.pdf

**[Source 6]** Title: 
- URL: https://www.reddit.com/r/LocalLLaMA/comments/1encx98/improved_text_to_speech_model_parler_tts_v1_by/

**[Source 7]** My Top 5 Open Source Text to Speech Softwares Starting off in 2024 - YouTube
- URL: https://www.youtube.com/watch?v=lPitjhhodaw

**[Source 8]** Gladia - Top 5 Open-Source Speech-to-Text Models for Enterprises
- URL: https://www.gladia.io/blog/best-open-source-speech-to-text-models

**[Source 9]** link to page 7 link to page 7 link to page 7 link to page 7 link to page 8 link to page 8 link to pa
- URL: https://aclanthology.org/2025.naacl-demo.12.pdf

**[Source 10]** Evaluating leading text-to-speech models
- URL: https://labelbox.com/guides/evaluating-leading-text-to-speech-models/

**[Source 11]** Title: 🎧 Listen and Compare 12 Open-Source Text-to-Speech Models (Hugging Face Space) : r/LocalLLaMA
- URL: https://www.reddit.com/r/LocalLLaMA/comments/1ltbrlf/listen_and_compare_12_opensource_texttospeech/

**[Source 12]** Title: 
- URL: https://www.reddit.com/r/MachineLearning/comments/1dcj439/n_how_good_do_you_think_this_new_open_source/

**[Source 13]** link to page 1 link to page 1 link to page 1 link to page 17 link to page 17 link to page 14 link to
- URL: https://aclanthology.org/2025.acl-long.682.pdf


---

**Metadata:**
- intent: comparative
- sections: ['Overview of Open-Weight Text-to-Speech Models', 'Key Models Compared: Architecture, Training Data, and Licensing', 'Performance Metrics and Quality Benchmarks', 'Computational Requirements and Inference Efficiency', 'Language and Accent Support', 'Ease of Use, Documentation, and Community Support', 'Limitations and Ethical Considerations', 'Recent Developments and Future Trends']
- status: complete
- num_sources: 13
- research_complete: True
