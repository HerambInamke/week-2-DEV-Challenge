# figma-make-app

React + Vite + Tailwind CSS project running inside Figma Make.

## Development Server

A Vite development server is **already running** on `$PORT` (default 8443). You don't need to start it manually.

- Preview URL: The user can access the running app through the preview panel
- Hot reload: Changes to source files are reflected immediately

## Project Structure

This is the canonical project structure. Start with task-relevant files below. Only follow imports or inspect other files when required, when a documented path is missing, or when the repository contradicts this guide.

- `client/src/main.tsx` - React entrypoint; imports `client/src/index.css` and mounts `client/src/App.tsx` into the `#root` element
- `client/src/App.tsx` - Primary application component and the usual starting point for UI work
- `client/src/index.css` - Global CSS entrypoint and Tailwind CSS v4 import
- `client/index.html` - Vite HTML shell containing the `#root` element and loading `client/src/main.tsx`
- `client/package.json` - Frontend dependencies and the Vite build, development, preview, and formatting scripts
- `client/vite.config.ts` - Vite configuration with React, Tailwind CSS v4, and Figma Make plugins plus the `@` alias for `client/src`
- `ai/` - Python AI engine, schemas, fixtures, and tests
- `.figma/make/` - Figma Make launch, build, deploy, and formatting scripts
- `.mise.toml` - Toolchain versions for Node.js and pnpm

## Dependencies

- Runtime: React 19 and React DOM 19
- Styling: Tailwind CSS v4 with the `@tailwindcss/vite` plugin
- Build tooling: Vite 8, TypeScript 5.7, and `@vitejs/plugin-react`
- Formatting: oxfmt

## Styling

This project uses **Tailwind CSS v4** through the `@tailwindcss/vite` plugin configured in `client/vite.config.ts`. `client/src/index.css` imports Tailwind with `@import 'tailwindcss';`. Use Tailwind utility classes directly in JSX and put global CSS or Tailwind v4 theme customization in `client/src/index.css`. This scaffold does not need a Tailwind config file or PostCSS config.

`client/src/main.tsx` imports `client/src/index.css`, so global font wiring belongs in `client/src/index.css`. Keep CSS `@import` statements first, then add any `@font-face` rules and font-family defaults there.

## Code quality

- Use double quotes for strings containing apostrophes (`"We're here to help"`), or escape them in single-quoted strings. An unescaped apostrophe in a single-quoted string breaks the build.
- Ensure JSX tags are closed and braces are balanced.
- Export components as default exports.
