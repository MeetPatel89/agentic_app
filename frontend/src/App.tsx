import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { History } from "./pages/History";
import { Playground } from "./pages/Playground";
import { RunDetail } from "./pages/RunDetail";

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Playground />} />
          <Route path="/history" element={<History />} />
          <Route path="/runs/:id" element={<RunDetail />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
