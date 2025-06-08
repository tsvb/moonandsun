self.onmessage = e => {
  const { cmd, data } = e.data;
  if (cmd === 'echo') {
    self.postMessage(data);
  }
};
