import { NavLink, Route, Routes } from "react-router";
import { ClaimPage } from "./ClaimPage";
import { InstructionsPage } from "./InstructionsPage";
import { QueuePage } from "./QueuePage";

export function App() {
  return (
    <>
      <header className="site-header">
        <NavLink to="/" className="brand">
          UnderCover <span className="tagline">Claims</span>
        </NavLink>
        <nav>
          <NavLink to="/" end>
            Queue
          </NavLink>
          <NavLink to="/instructions">Instructions</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<QueuePage />} />
          <Route path="/claims/:claimId" element={<ClaimPage />} />
          <Route path="/instructions" element={<InstructionsPage />} />
        </Routes>
      </main>
    </>
  );
}
