# SwasthGati - Web Knee Risk Screening Prototype + Smirthi Cognitive Platform

This project contains two healthcare modules:

1. **SwasthGati** — browser-based knee (osteoarthritis) screening with real webcam, photo upload, and video upload analysis using YOLO pose detection.
2. **Smirthi** — an AI-powered cognitive gaming and memory-assistance platform for elderly dementia patients in the North Eastern Region (NER).

## Requirements

Install the runtime dependencies:

```powershell
cd E:\SIH2026
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the web app

```powershell
cd E:\SIH2026
.\.venv\Scripts\Activate.ps1
python web_app.py
```

Or double-click:

```powershell
E:\SIH2026\run_demo.bat     # SwasthGati knee screening
E:\SIH2026\run_cognitive.bat  # Smirthi cognitive companion
```

Then open the browser at:

```text
http://127.0.0.1:5000           # SwasthGati knee screening
http://127.0.0.1:5000/cognitive # Smirthi cognitive games
```

## Smirthi - Cognitive Platform Features

### Interactive Cognitive Games (a)
- **Memory Match** — flip and match culturally-familiar picture pairs (flowers, animals, festivals, food, nature)
- **Word Memory** — remember and recall a sequence of everyday words
- **Pattern Finder** — identify what comes next in a visual pattern
- **Daily Routine** — arrange daily activities (wake, medicine, meals, sleep) in correct order
- **Object Finder** — locate the target object among choices
- **Color Match** — tap the colour that matches the spoken/displayed name

### AI / ML Adaptive Difficulty (b)
- `AdaptiveDifficultyEngine` raises/lowers difficulty (grid size, sequence length, options, time) based on accuracy — level up on ≥90% accuracy, level down on ≤55%.
- Next difficulty level is computed and returned after every session.

### Multilingual & Voice-Assisted (c, d)
- Languages: English, Hindi, Assamese, Bengali, Meiteilon (Manipuri), Khasi, Mizo.
- Browser speech synthesis reads instructions, praise and results aloud; per-game "Listen" buttons.
- Culturally familiar NER emoji themes, warm earthy palette, simple layout.

### Reminders (e)
- Medicines, hydration, daily activities and appointments.
- Default schedule auto-seeded per patient; add/toggle/delete; time-of-day scheduling and acknowledgement logs.

### Caregiver Monitoring (f)
- `/cognitive#caregiver` dashboard: cognitive health score, engagement time, accuracy, weekly activity bars, session lists, and alerts (declining trend, inactivity).

### Offline Support (g)
- Service worker (`static/sw.js`) caches the PWA shell; game puzzles cached for offline plays.
- Offline sessions queued in localStorage and auto-synced when connectivity returns.

### Elderly-Friendly & Accessible (h)
- Large touch targets, big fonts, optional **Large Text** and **High Contrast** modes, warm high-contrast palette, minimal distractions, tablet/mobile responsive.

### Cognitive Tracking & Analytics
- Every game session stored (score, accuracy, time, adaptive level). Patient overall stats, per-game breakdown, daily engagement, 30-day trend ("improving / stable / declining") and cognitive assessments.

## Smirthi Backend Modules

- `modules/cognitive_games.py` — game generators + adaptive difficulty engine
- `modules/cognitive_db.py` — SQLite storage for patients, sessions, assessments, reminders, daily activities
- `modules/reminders.py` — reminder service + caregiver analytics
- `modules/ner_translations.py` — NER-language UI content bundles
- API routes in `web_app.py` under `/api/cognitive/*`
- Front-end: `templates/cognitive.html`, `static/cognitive.js`, `static/cognitive.css`, `static/sw.js`, `static/manifest.json`

## SwasthGati Features

- Live browser webcam with real pose overlay and knee angle updates
- Photo upload analysis with real landmark detection
- Video upload analysis with processed output export
- Clear result cards with non-diagnostic screening language
- Handles no person, insufficient landmarks, and multiple people warnings

## Notes

- SwasthGati is a screening prototype, not a medical diagnosis.
- Smirthi is a cognitive support and early-intervention tool, not a clinical dementia diagnostic.
- Metrics are calculated from real pose landmarks and real user gameplay (no simulation).
- The architecture stays modular for future IMU/X-ray fusion and cloud sync support.
