/* Small, dependency-free BM25 index shared by the app, portable guides, and benchmarks. */
(function (root) {
  'use strict';
  const terms = value => String(value || '').normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase().match(/[\p{L}\p{N}]+/gu) || [];
  class ProfileSearch {
    constructor(people) {
      this.people = people;
      this.postings = new Map();
      this.lengths = [];
      people.forEach((p, id) => {
        const facts = (p.professional?.facts || []).map(f => f.value).join(' ');
        const words = terms([p.name, p.name, p.name, facts, facts, p.summary, ...(p.why || [])].join(' '));
        this.lengths.push(words.length);
        const counts = new Map();
        words.forEach(word => counts.set(word, (counts.get(word) || 0) + 1));
        for (const [word, frequency] of counts) {
          if (!this.postings.has(word)) this.postings.set(word, new Map());
          this.postings.get(word).set(id, frequency);
        }
      });
      this.average = this.lengths.reduce((a, b) => a + b, 0) / (people.length || 1) || 1;
      this.vocabulary = [...this.postings.keys()].sort();
    }
    prefix(value) {
      let low = 0, high = this.vocabulary.length;
      while (low < high) {
        const mid = (low + high) >>> 1;
        if (this.vocabulary[mid] < value) low = mid + 1; else high = mid;
      }
      const matches = [];
      while (low < this.vocabulary.length && this.vocabulary[low].startsWith(value)) matches.push(this.vocabulary[low++]);
      return matches;
    }
    search(query) {
      const words = [...new Set(terms(query))];
      if (!words.length) return this.people.map((person, id) => ({person, id, score: 0}));
      let candidates = null;
      words.forEach((word, index) => {
        const variants = index === words.length - 1 && word.length >= 2 ? this.prefix(word) : [word];
        const scores = new Map();
        for (const variant of variants) {
          const posting = this.postings.get(variant);
          if (!posting) continue;
          const idf = Math.log(1 + (this.people.length - posting.size + .5) / (posting.size + .5));
          for (const [id, frequency] of posting) {
            const score = idf * frequency * 2.2 / (frequency + 1.2 * (.25 + .75 * this.lengths[id] / this.average));
            scores.set(id, Math.max(scores.get(id) || 0, score));
          }
        }
        if (candidates === null) candidates = scores;
        else for (const [id, score] of candidates) {
          if (!scores.has(id)) candidates.delete(id); else candidates.set(id, score + scores.get(id));
        }
      });
      return [...(candidates || [])].map(([id, score]) => ({person: this.people[id], id, score}))
        .sort((a, b) => b.score - a.score || a.id - b.id);
    }
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = ProfileSearch;
  else root.ProfileSearch = ProfileSearch;
})(typeof window === 'undefined' ? this : window);
