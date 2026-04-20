# `env.d.ts`

Create `env.d.ts` at the webapp root:

```ts
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_PORT: string
  readonly VITE_CLIENT_PORT: string
}
```
