/** Used only to generate the compiled tailwind.generated.css below —
 *  not part of the shipped runtime (no CDN script, no build step at
 *  request time). Re-run `npx tailwindcss@3 -c tailwind.config.js
 *  -i tailwind.input.css -o tailwind.generated.css --minify` after
 *  changing classes in index.html or admin.js. */
module.exports = {
  content: ['./index.html', './admin.js'],
  theme: {
    extend: {
      colors: {
        sidebar: '#0F2017',
        'sidebar-hover': '#17301F',
        accent: '#2D6A4F',
        'accent-light': '#52B788',
        cream: '#F7F5EF',
      },
    },
  },
  plugins: [],
};
