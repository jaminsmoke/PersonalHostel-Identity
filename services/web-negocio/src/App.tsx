import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Carta } from "./components/Carta";
import { Contacto } from "./components/Contacto";
import { Equipo } from "./components/Equipo";
import { Galeria } from "./components/Galeria";
import { Hero } from "./components/Hero";
import { Horario } from "./components/Horario";
import { Nosotros } from "./components/Nosotros";
import { PantallaError, WebLayout } from "./WebLayout";

function HomePage() {
  return (
    <>
      <Hero />
      <Nosotros />
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/negocios/:slug" element={<WebLayout />}>
          <Route index element={<HomePage />} />
          <Route path="horario" element={<Horario />} />
          <Route path="carta" element={<Carta />} />
          <Route path="equipo" element={<Equipo />} />
          <Route path="contacto" element={<Contacto />} />
          <Route path="galeria" element={<Galeria />} />
        </Route>
        <Route path="/" element={<PantallaError />} />
        <Route path="*" element={<PantallaError />} />
      </Routes>
    </BrowserRouter>
  );
}
