(function () {
    'use strict';

    const pending = new WeakMap();

    async function fetchFragments(root) {
        try {
            const url = new URL(root.dataset.personalisationUrl, window.location.href);
            if (url.origin !== window.location.origin) {
                throw new Error('Personalisation fragments must use the same origin.');
            }
            const response = await fetch(url, {
                credentials: 'same-origin',
                mode: 'same-origin',
                cache: 'no-store',
                headers: {
                    'X-Personalisation-Page-Url': window.location.href,
                    'X-Personalisation-Referrer': document.referrer,
                },
            });
            if (!response.ok) {
                throw new Error('Personalisation fragments could not be loaded.');
            }
            const container = document.createElement('template');
            container.innerHTML = await response.text();
            const slots = root.querySelectorAll('[data-personalisation-slot]');
            container.content.querySelectorAll('template[data-personalisation-fragment]').forEach((fragment) => {
                slots.forEach((slot) => {
                    if (slot.dataset.personalisationSlot === fragment.dataset.personalisationFragment) {
                        slot.replaceChildren(fragment.content.cloneNode(true));
                        slot.dispatchEvent(new CustomEvent('personalisation:loaded', {
                            bubbles: true,
                            detail: { name: fragment.dataset.personalisationFragment },
                        }));
                    }
                });
            });
            return true;
        } catch (error) {
            root.dispatchEvent(new CustomEvent('personalisation:error', {
                bubbles: true,
                detail: { error },
            }));
            return false;
        }
    }

    function load(root) {
        if (!pending.has(root)) {
            pending.set(root, Promise.resolve().then(() => fetchFragments(root)));
        }
        return pending.get(root);
    }

    window.wagtailPersonalisation = { load };

    function initialise() {
        document.querySelectorAll('[data-personalisation-url]').forEach(load);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialise, { once: true });
    } else {
        initialise();
    }
}());
