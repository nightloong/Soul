import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { expect, test } from 'vitest'
import { AppRoutes } from './App'

test('shows the application and API status', () => {
  const html = renderToStaticMarkup(<MemoryRouter initialEntries={['/datasets']}><AppRoutes /></MemoryRouter>)
  expect(html).toContain('PersonaForge')
  expect(html).toContain('API:')
})
