# Adding a Memory News article

1. Save the article HTML in the site root.
2. Add its entry to `news-articles.json`: `slug` (filename without `.html`), `title`, `summary`, `category`, and `date` (`YYYY-MM-DD`). Use `null` only for undated guides.
3. Run from the site root:

   ```sh
   python3 scripts/update-news.py
   ```

4. Push the article, the JSON list, and the updated `index.html`, `memory-news.html`, and `sitemap.xml` together.

The homepage shows the three newest entries. Memory News shows the complete list. Dated articles sort newest first, followed by undated guides in list order. No page redesign, browser JavaScript, or hosting build setup is required. Run this command whenever adding or editing a listing; it does not discover article files automatically. Avoid editing generated listing regions by hand.
