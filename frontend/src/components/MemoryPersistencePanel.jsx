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

function formatSavedAt(value) {
  if (!value) return '-';
  try {
    return new Date(value).toLocaleString('ko-KR');
  } catch (error) {
    return value;
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

export default function MemoryPersistencePanel({ character, saveRequest }) {
  const [saved, setSaved] = useState(null);
  const [statusText, setStatusText] = useState('');
  const [ignoredKeys, setIgnoredKeys] = useState({});

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
      if (record && record.__key === memoryKey) {
        setSaved(record);
        setIgnoredKeys((prev) => ({ ...prev, [record.__key]: false }));
      }
      setStatusText('현재 기억 기록을 이 브라우저에 저장했습니다.');
    } catch (error) {
      setStatusText('브라우저 저장소에 기록을 저장하지 못했습니다.');
    }
  }, [saveRequest, memoryKey]);

  if (!character || !memoryKey) return null;

  const isIgnored = Boolean(ignoredKeys[memoryKey]);
  const visibleSaved = saved && !isIgnored ? saved : null;

  function loadMemory() {
    if (!saved?.memoryHints) return;
    try {
      window.dispatchEvent(new CustomEvent('loa-hsi-load-memory-hints', {
        detail: { memoryHints: cloneJson(saved.memoryHints), character }
      }));
      setIgnoredKeys((prev) => ({ ...prev, [memoryKey]: false }));
      setStatusText('저장된 기억 기록을 화면 입력값에 반영했습니다.');
    } catch (error) {
      setStatusText('저장된 기억 기록을 불러오지 못했습니다.');
    }
  }

  function ignoreMemory() {
    setIgnoredKeys((prev) => ({ ...prev, [memoryKey]: true }));
    setStatusText('이번 세션에서 저장 기록을 무시합니다.');
  }

  function unignoreMemory() {
    setIgnoredKeys((prev) => ({ ...prev, [memoryKey]: false }));
    setStatusText('저장 기록을 다시 표시합니다.');
  }

  function deleteMemory() {
    try {
      window.localStorage.removeItem(memoryKey);
      setSaved(null);
      setIgnoredKeys((prev) => ({ ...prev, [memoryKey]: false }));
      setStatusText('저장된 기억 기록을 삭제했습니다.');
    } catch (error) {
      setStatusText('저장된 기억 기록을 삭제하지 못했습니다.');
    }
  }

  return (
    <div className="notice-panel loa-hsi-memory-panel" data-loa-hsi-memory-panel="true">
      <strong>기억 기록 저장 상태</strong>
      <p className="hint">v58부터 기억 기반 보조 판정은 서버가 아니라 이 브라우저 localStorage에만 저장합니다. 클라우드 배포 후에도 다른 사용자와 공유되지 않습니다.</p>

      {visibleSaved ? (
        <>
          <p className="hint">이 캐릭터에 저장된 기록이 있습니다. 마지막 저장: {formatSavedAt(visibleSaved.savedAt)}</p>
          <div className="row">
            <button type="button" className="ghost tiny-button" onClick={loadMemory}>불러오기</button>
            <button type="button" className="ghost tiny-button" onClick={ignoreMemory}>무시</button>
            <button type="button" className="ghost tiny-button" onClick={deleteMemory}>삭제</button>
          </div>
        </>
      ) : isIgnored ? (
        <>
          <p className="hint">이번 세션에서는 저장된 기록을 무시합니다. 리포트 생성 시 현재 입력값이 다시 저장됩니다.</p>
          <div className="row"><button type="button" className="ghost tiny-button" onClick={unignoreMemory}>다시 보기</button></div>
        </>
      ) : (
        <p className="hint">저장된 기록이 없습니다. 억까 리포트 생성 시 현재 입력값이 자동 저장됩니다.</p>
      )}

      {statusText && <p className="hint"><strong>{statusText}</strong></p>}
    </div>
  );
}
