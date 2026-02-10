---
name: voice
description: Change the TTS voice for speak()
user_invocable: true
argument-hint: "[voice name]"
---

Help the user pick a Kokoro TTS voice. If they provided a voice name as $ARGUMENTS, confirm that choice. Otherwise, show them the options below and ask which they'd like.

## Available voices

### English (American) — lang "a"
**Female:** af_alloy, af_aoede, af_bella, af_heart (default), af_jessica, af_kore, af_nicole, af_nova, af_river, af_sarah, af_sky
**Male:** am_adam, am_echo, am_eric, am_fenrir, am_liam, am_michael, am_onyx, am_puck

### English (British) — lang "b"
**Female:** bf_alice, bf_emma, bf_isabella, bf_lily
**Male:** bm_daniel, bm_fable, bm_george, bm_lewis

### Hindi — lang "h"
**Female:** hf_alpha, hf_beta
**Male:** hm_omega, hm_psi

### Spanish — lang "e"
**Female:** ef_dora
**Male:** em_alex

### French — lang "f"
**Female:** ff_siwis

### Italian — lang "i"
**Female:** if_sara
**Male:** im_nicola

### Japanese — lang "j"
**Female:** jf_alpha, jf_gongitsune, jf_nezumi, jf_tebukuro
**Male:** jm_kumo

### Portuguese — lang "p"
**Female:** pf_dora
**Male:** pm_alex

### Mandarin Chinese — lang "z"
**Female:** zf_xiaobei, zf_xiaoni, zf_xiaoxiao, zf_xiaoyi
**Male:** zm_yunjian, zm_yunxi, zm_yunxia, zm_yunyang

## Voice naming convention
- First letter = language (a=American, b=British, h=Hindi, etc.)
- Second letter = gender (f=female, m=male)
- Rest = voice name

Once the user picks a voice, demonstrate it by calling speak() with a short sample sentence using that voice. Remind them they can change it anytime with `/voice`.
