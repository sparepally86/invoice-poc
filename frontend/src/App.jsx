// src/App.jsx
import React from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";

export default function App() {
  return (
    <div className="app-layout">
      <Sidebar />
      
      <div className="main-content">
        <Header />
        
        <div className="content-area">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
