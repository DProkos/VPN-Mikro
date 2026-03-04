# Update Server Setup

Αυτό το έγγραφο εξηγεί πώς να ρυθμίσεις τον server για auto-updates.

## Αρχείο update.json

Το πρόγραμμα ελέγχει για updates διαβάζοντας ένα JSON αρχείο από τον server σου.

### Δομή του update.json

```json
{
    "version": "1.0.0",
    "download_url": "https://your-server.com/downloads/vpnmikro-setup-1.0.0.exe",
    "changelog": "Νέα χαρακτηριστικά:\n- Feature 1\n- Feature 2\n\nΔιορθώσεις:\n- Bug fix 1",
    "release_date": "2025-12-26",
    "min_version": "0.0.1"
}
```

### Πεδία

| Πεδίο | Περιγραφή |
|-------|-----------|
| `version` | Η νέα έκδοση (π.χ. "1.0.0") |
| `download_url` | URL για download του installer (.exe) |
| `changelog` | Τι νέο υπάρχει στην έκδοση (χρησιμοποίησε `\n` για νέες γραμμές) |
| `release_date` | Ημερομηνία κυκλοφορίας (YYYY-MM-DD) |
| `min_version` | Ελάχιστη έκδοση που μπορεί να κάνει upgrade (προαιρετικό) |

## Ρύθμιση URL

Άλλαξε το URL στο αρχείο `vpnmikro/core/updater.py`:

```python
UPDATE_URL = "https://your-server.com/update.json"
```

## Παραδείγματα

### Παράδειγμα 1: Τρέχουσα έκδοση (δεν υπάρχει update)

```json
{
    "version": "0.0.1",
    "download_url": "https://your-server.com/downloads/vpnmikro-setup-0.0.1.exe",
    "changelog": "Initial Release",
    "release_date": "2025-12-26",
    "min_version": "0.0.0"
}
```

### Παράδειγμα 2: Νέα έκδοση διαθέσιμη

```json
{
    "version": "1.0.0",
    "download_url": "https://your-server.com/downloads/vpnmikro-setup-1.0.0.exe",
    "changelog": "Version 1.0.0:\n\nΝέα χαρακτηριστικά:\n- Αυτόματο update\n- Βελτιωμένο UI\n- Startup με Windows\n\nΔιορθώσεις:\n- Διόρθωση MikroTik σύνδεσης\n- Διόρθωση tray icon",
    "release_date": "2025-12-27",
    "min_version": "0.0.1"
}
```

### Παράδειγμα 3: Major update με breaking changes

```json
{
    "version": "2.0.0",
    "download_url": "https://your-server.com/downloads/vpnmikro-setup-2.0.0.exe",
    "changelog": "Version 2.0.0 - Major Update:\n\n⚠️ ΣΗΜΑΝΤΙΚΟ: Απαιτείται επανεγκατάσταση\n\nΝέα χαρακτηριστικά:\n- Νέο UI design\n- Multi-language support\n- Cloud sync",
    "release_date": "2026-01-15",
    "min_version": "1.0.0"
}
```

## Hosting Options

### GitHub Pages (Δωρεάν)

1. Δημιούργησε ένα repository στο GitHub
2. Ανέβασε το `update.json` στο root
3. Ενεργοποίησε GitHub Pages
4. URL: `https://username.github.io/repo-name/update.json`

### GitHub Raw (Δωρεάν)

1. Ανέβασε το `update.json` στο repository
2. URL: `https://raw.githubusercontent.com/username/repo-name/main/update.json`

### Δικός σου Server

1. Ανέβασε το `update.json` σε οποιοδήποτε web server
2. Βεβαιώσου ότι επιστρέφει `Content-Type: application/json`

## Διαδικασία Release

1. Κάνε build το νέο installer με `python build.py`
2. Ανέβασε το installer στον server
3. Ενημέρωσε το `update.json` με τη νέα version και download URL
4. Οι χρήστες θα δουν το update αυτόματα ή με "Check for Updates"

## Troubleshooting

### 404 Not Found
- Έλεγξε ότι το URL είναι σωστό
- Έλεγξε ότι το αρχείο υπάρχει στον server

### Δεν εμφανίζεται update
- Έλεγξε ότι η version στο JSON είναι μεγαλύτερη από την τρέχουσα
- Έλεγξε ότι το JSON είναι valid (χρησιμοποίησε jsonlint.com)

### Download αποτυγχάνει
- Έλεγξε ότι το download_url είναι σωστό
- Έλεγξε ότι ο server επιτρέπει downloads
