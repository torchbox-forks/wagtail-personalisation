const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const sourcePath = path.join(__dirname, '../../src/wagtail_personalisation/static/wagtail_personalisation/js/fragments.js');

function browser({ status = 200, url = '/fragments/12/', reject = false } = {}) {
    const events = [];
    const requests = [];
    let contents = 'Fallback content';
    const slot = {
        dataset: { personalisationSlot: 'message' },
        replaceChildren: (content) => { contents = content; },
        dispatchEvent: (event) => { events.push(event); },
    };
    const root = {
        dataset: { personalisationUrl: url },
        querySelectorAll: () => [slot],
        dispatchEvent: (event) => { events.push(event); },
    };
    const document = {
        readyState: 'complete',
        referrer: 'https://search.example/results',
        querySelectorAll: () => [root],
        createElement: () => ({
            content: {
                querySelectorAll: () => [{
                    dataset: { personalisationFragment: 'message' },
                    content: { cloneNode: () => 'Personalised HTML' },
                }],
            },
        }),
    };
    const window = { location: new URL('https://site.example/course/?audience=student') };
    vm.runInNewContext(fs.readFileSync(sourcePath, 'utf8'), {
        window, document, URL, WeakMap,
        CustomEvent: class { constructor(type, options) { this.type = type; Object.assign(this, options); } },
        fetch: async (url, options) => {
            requests.push({ url, options });
            if (reject) throw new Error('Network error');
            return { ok: status === 200, text: async () => 'Fragment HTML' };
        },
    });
    return { window, root, events, requests, contents: () => contents };
}

test('loads once, forwards original navigation and announces inserted content', async () => {
    const app = browser();
    assert.equal(await app.window.wagtailPersonalisation.load(app.root), true);
    assert.equal(app.requests.length, 1);
    const { url, options } = app.requests[0];
    assert.equal(url.origin, 'https://site.example');
    assert.equal(options.credentials, 'same-origin');
    assert.equal(options.cache, 'no-store');
    assert.equal(options.mode, 'same-origin');
    assert.equal(options.headers['X-Personalisation-Page-Url'], 'https://site.example/course/?audience=student');
    assert.equal(options.headers['X-Personalisation-Referrer'], 'https://search.example/results');
    assert.equal(app.contents(), 'Personalised HTML');
    assert.equal(app.events.length, 1);
    assert.equal(app.events[0].type, 'personalisation:loaded');
    assert.equal(app.events[0].bubbles, true);
    await app.window.wagtailPersonalisation.load(app.root);
    assert.equal(app.requests.length, 1);
});

for (const failure of [{ status: 500 }, { reject: true }, { url: 'https://other.example/fragments/' }]) {
    test(`preserves fallback content on ${JSON.stringify(failure)}`, async () => {
        const app = browser(failure);
        assert.equal(await app.window.wagtailPersonalisation.load(app.root), false);
        assert.equal(app.contents(), 'Fallback content');
        assert.equal(app.events[0].type, 'personalisation:error');
        if (failure.url) assert.equal(app.requests.length, 0);
    });
}
