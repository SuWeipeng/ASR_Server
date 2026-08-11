import React from 'react';
import ReactDOM from 'react-dom/client';
import { Provider } from 'react-redux';
import store from './store';
import App from './App.jsx';
import { PlayerWindowApp } from './PlayerWindowApp';
import './styles/globals.css';

// 检查是否是播放器窗口模式
const urlParams = new URLSearchParams(window.location.search);
const isPlayerWindow = urlParams.get('mode') === 'player';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Provider store={store}>
      {isPlayerWindow ? <PlayerWindowApp /> : <App />}
    </Provider>
  </React.StrictMode>
);
