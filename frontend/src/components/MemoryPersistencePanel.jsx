import React, { useEffect, useMemo, useState } from 'react';

function characterNameOf(character) {
  return String((character && (character.character_name || character.characterName)) || '').trim();
}

function serverNameOf(character) {
  return String((character && (character.server_name || character.serverName)) || 'unknown').trim() || 'unknown';
}

function memoryKeyFor(characterName, serverName) {
  return `loa-hsi:memory:v1:${encodeURIComponent(serverName || 'unknown')}:${encodeURIComponent(characterName || 'unknown')}`;
}

function cloneJson(value) {
  try {
    return JSON.parse(JSON.stringify(value || {}));
  } catch (error) {
    return {};
  }
}

function readSavedMemory(character) {
  const characterName = characterNameOf(character);
  if (!characterName) return null;
  const key = memoryKeyFor(characterName, serverNameOf(character));
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return { ...parsed, __key: key };
  } catch (error) {
    return null;
  }
}

function writeMemoryRecord(character, memoryHints) {
  const characterName = characterNameOf(character);
  if (!characterName || !memoryHints) return null;
  const serverName = serverNameOf(character);
  const key = memoryKeyFor(characterName, serverName);
  const record = {
    version: 1,
    characterName,
    serverName,
    savedAt: new Date().toISOString(),
    memoryHints: cloneJson(memoryHints)
  };
  window.localStorage.setItem(key, JSON.stringify(record));
  return { ...record, __key: key };
}

export default function MemoryPersistencePanel({ character, saveRequest, onLoadMemoryHints }) {
  const [saved, setSaved] = useState(null);
  const [statusText, setStatusText] = useState('');

  const memoryKey = useMemo(() => {
    const name = characterNameOf(character);
    if (!name) return '';
    return memoryKeyFor(name, serverNameOf(character));
  }, [character]);

  useEffect(() => {
    if (!memoryKey) {
      setSaved(null);
      setStatusText('');
      return;
    }
    setSaved(readSavedMemory(character));
    setStatusText('');
  }, [character, memoryKey]);

  useEffect(() => {
    if (!saveRequest?.id || !saveRequest?.character || !saveRequest?.memoryHints) return;
    try {
      const record = writeMemoryRecord(saveRequest.character, saveRequest.memoryHints);
      if (record && record.__key === memoryKey) setSaved(record);
      setStatusText('저장 완료');
    } catch (error) {
      setStatusText('저장 실패');
    }
  }, [saveRequest, memoryKey]);

  if (!character || !memoryKey) return null;

  function loadMemory() {
    if (!saved?.memoryHints) return;
    try {
      onLoadMemoryHints?.(cloneJson(saved.memoryHints), character);
      setStatusText('불러옴');
    } catch (error) {
      setStatusText('불러오기 실패');
    }
  }

  function deleteMemory() {
    try {
      window.localStorage.removeItem(memoryKey);
      setSaved(null);
      setStatusText('삭제 완료');
    } catch (error) {
      setStatusText('삭제 실패');
    }
  }

  return (
    <div className="notice-panel loa-hsi-memory-panel" data-loa-hsi-memory-panel="true">
      <div className="row compact-memory-row">
        <strong>기억 기록</strong>
        {saved ? (
          <span className="row">
            <button type="button" className="ghost tiny-button" onClick={loadMemory}>불러오기</button>
            <button type="button" className="ghost tiny-button" onClick={deleteMemory}>삭제</button>
          </span>
        ) : (
          <small className="hint">저장 없음</small>
        )}
        {statusText && <small className="hint">{statusText}</small>}
      </div>
    </div>
  );
}
