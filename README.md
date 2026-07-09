# Grafida — AI βοηθός για Έλληνες δικηγόρους (MVP slice)

**Το AI βοηθά — ο δικηγόρος αποφασίζει.** Κάθε παραγόμενο έγγραφο απαιτεί έλεγχο,
επεξεργασία και έγκριση από δικηγόρο πριν από οποιαδήποτε χρήση.

## Προαπαιτούμενα

- Docker Desktop (Windows/Mac/Linux)
- [Ollama](https://ollama.com) εγκατεστημένο **στον host** (όχι σε container, ώστε
  να χρησιμοποιεί GPU):
  ```
  ollama pull qwen2.5:7b
  ollama pull bge-m3
  ```
  Προαιρετικά δοκιμάστε ελληνικό μοντέλο και ορίστε `AI_CHAT_MODEL` στο `.env`.

## Εκτέλεση

```
cp .env.example .env      # και αλλάξτε το JWT_SECRET
docker compose up --build
```

- Εφαρμογή: http://localhost:3000 — σύνδεση με `SEED_EMAIL` / `SEED_PASSWORD` από το `.env`.
- API: http://localhost:8000/docs

## Tests

```
docker compose run --rm backend pytest -q
```

(Θα συμπληρωθεί με πλήρες σενάριο E2E στο τέλος της υλοποίησης.)
