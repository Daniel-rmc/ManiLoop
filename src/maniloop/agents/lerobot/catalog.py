"""Reviewed public checkpoints; revisions are immutable Hub commits."""

MODELS = {
    "smolvla-libero": {
        "repo": "lerobot/smolvla_libero",
        "revision": "31d453f7edd78c839a8bbc39744a292686daf0de",
        "family": "smolvla",
        "publisher": "official",
        "language_conditioned": True,
    },
    "act-libero": {
        "repo": "Deepkar/libero-test-act",
        "revision": "b6a5253edf0c9d9e458629fdeb489f514ff6300f",
        "family": "act",
        "publisher": "community",
        "language_conditioned": False,
    },
    "diffusion-libero": {
        "repo": "ttotmoon/diffusion-libero-v3",
        "revision": "5825af28c585ade6827ea7e8f6234f3ab04e8ab1",
        "family": "diffusion",
        "publisher": "community",
        "language_conditioned": False,
    },
}
TOKENIZER = {
    "repo": "HuggingFaceTB/SmolVLM2-500M-Video-Instruct",
    "revision": "7b375e1b73b11138ff12fe22c8f2822d8fe03467",
}
