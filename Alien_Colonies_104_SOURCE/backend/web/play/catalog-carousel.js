// Preserve the card, its reading position and ship quantities across refreshes.
// Each mount owns its view object, so a new colony cannot overwrite the old one.
export function mountCatalogCarousels(root, views = {}, {onBatch = () => {}} = {}) {
  const tracks = [...root.querySelectorAll('[data-catalog-carousel]')];
  const cleanups = [];
  for (const track of tracks) {
    const key = track.dataset.catalogCarousel;
    const view = views[key] ||= {};
    const cards = [...track.querySelectorAll('[data-catalog-card]')];
    const scrollers = cards.map(card => ({card,body:card.querySelector?.('[data-card-scroll]') || card}));
    const section = track.closest('[data-carousel-section]');
    const previous = section.querySelector('[data-carousel-step="-1"]');
    const next = section.querySelector('[data-carousel-step="1"]');
    const position = card => card.getBoundingClientRect().left-track.getBoundingClientRect().left+track.scrollLeft;
    const updateButtons = () => {
      previous.disabled = track.scrollLeft <= 1;
      next.disabled = track.scrollLeft >= track.scrollWidth-track.clientWidth-1;
    };
    const save = () => {
      view.left = track.scrollLeft;
      const anchor = cards.reduce((best, card) => !best || Math.abs(position(card)-view.left)<Math.abs(position(best)-view.left) ? card : best, null);
      if (anchor) { view.anchor = anchor.dataset.catalogCard; view.offset = view.left-position(anchor); }
      const scrollTops = Object.fromEntries(scrollers.filter(({body}) => Number(body.scrollTop) > 0).map(({card,body}) => [card.dataset.catalogCard,body.scrollTop]));
      if (Object.keys(scrollTops).length) view.scrollTops = scrollTops;
      else delete view.scrollTops;
      view.batches = Object.fromEntries([...track.querySelectorAll('[data-batch]')].map(input => [input.dataset.batch,input.value]));
      updateButtons();
    };
    for (const input of track.querySelectorAll('[data-batch]')) {
      if (Object.hasOwn(view.batches || {}, input.dataset.batch)) {
        input.value = view.batches[input.dataset.batch];
        onBatch(input);
      }
    }
    const anchor = cards.find(card => card.dataset.catalogCard === view.anchor);
    track.scrollLeft = anchor ? position(anchor)+(Number(view.offset)||0) : Number(view.left)||0;
    const move = event => {
      const button = event.target.closest('[data-carousel-step]');
      if (!button || button.disabled) return;
      const direction = Number(button.dataset.carouselStep);
      const current = cards.reduce((best,card,index) => Math.abs(position(card)-track.scrollLeft)<Math.abs(position(cards[best])-track.scrollLeft) ? index : best,0);
      const target = cards[Math.max(0,Math.min(cards.length-1,current+direction))];
      if (target) track.scrollTo({left:position(target),behavior:document.documentElement.classList.contains('reduce-motion')?'instant':'smooth'});
    };
    const fitArtwork = () => {
      if (!track.clientHeight) return;
      const available = track.clientHeight - 13;
      for (const card of cards) {
        const footer = card.querySelector?.('.construction-card-footer');
        // Reserve readable text and all buying controls even on short landscape screens.
        const textSpace = Math.min(128,Math.max(64,available * .22));
        const maxHeight = Math.max(24,available - (footer?.offsetHeight || 0) - textSpace);
        card.style?.setProperty('--card-art-max-height',`${maxHeight}px`);
      }
    };
    const observer = new ResizeObserver(() => { fitArtwork(); updateButtons(); });
    observer.observe(track);
    cards.forEach(card => { const footer=card.querySelector?.('.construction-card-footer'); if(footer)observer.observe(footer); });
    fitArtwork();
    for (const {card,body} of scrollers) {
      body.scrollTop = Number(view.scrollTops?.[card.dataset.catalogCard]) || 0;
      body.addEventListener('scroll',save,{passive:true});
    }
    track.addEventListener('scroll',save,{passive:true});
    track.addEventListener('input',save);
    section.addEventListener('click',move);
    updateButtons();
    cleanups.push(() => { save(); observer.disconnect(); scrollers.forEach(({body})=>body.removeEventListener('scroll',save)); track.removeEventListener('scroll',save); track.removeEventListener('input',save); section.removeEventListener('click',move); });
  }
  return {destroy(){cleanups.forEach(cleanup=>cleanup());}};
}
