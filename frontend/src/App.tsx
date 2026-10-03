import { Route, Routes } from 'react-router-dom'
import Landing from './pages/Landing'
import Platform from './pages/Platform'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/platform" element={<Platform />} />
      <Route path="*" element={<Landing />} />
    </Routes>
  )
}
