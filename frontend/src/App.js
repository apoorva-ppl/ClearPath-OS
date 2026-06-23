import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import NavBar from "@/components/clearpath/NavBar";
import CommandPalette from "@/components/clearpath/CommandPalette";
import CursorGlow from "@/components/clearpath/CursorGlow";
import Landing from "@/pages/Landing";
import GodMode from "@/pages/GodMode";
import Sentinel from "@/pages/Sentinel";
import Intelligence from "@/pages/Intelligence";
import Debrief from "@/pages/Debrief";
import VulnerableZone from "@/pages/Vulnerablezone";

function Shell() {
    const loc = useLocation();
    const [cmd, setCmd] = useState(false);
    const showNav = loc.pathname !== "/";

    useEffect(() => {
        const onKey = (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
                e.preventDefault();
                setCmd((c) => !c);
            }
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, []);

    return (
        <>
            <CursorGlow />
            {showNav && <NavBar onCmd={() => setCmd(true)} />}
            <div key={loc.pathname} className="page-enter">
                <Routes>
                    <Route path="/" element={<Landing />} />
                    <Route path="/god-mode" element={<GodMode />} />
                    <Route path="/sentinel" element={<Sentinel />} />
                    <Route path="/intelligence" element={<Intelligence />} />
                    <Route path="/debrief" element={<Debrief />} />
                    <Route path="/vulnerable" element={<VulnerableZone />} />
                </Routes>
            </div>
            <CommandPalette open={cmd} onClose={() => setCmd(false)} />
        </>
    );
}

export default function App() {
    return (
        <BrowserRouter>
            <Shell />
        </BrowserRouter>
    );
}
