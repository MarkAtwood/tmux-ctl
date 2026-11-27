class TmuxCtl < Formula
  include Language::Python::Virtualenv

  desc "HTTP API for tmux automation and AI agents"
  homepage "https://github.com/MarkAtwood/tmux-ctl"
  url "https://files.pythonhosted.org/packages/source/t/tmux-ctl/tmux_ctl-0.1.0.tar.gz"
  sha256 "PLACEHOLDER"
  license "MIT"

  depends_on "python@3.12"
  depends_on "tmux"

  resource "fastapi" do
    url "https://files.pythonhosted.org/packages/source/f/fastapi/fastapi-0.115.0.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "uvicorn" do
    url "https://files.pythonhosted.org/packages/source/u/uvicorn/uvicorn-0.30.0.tar.gz"
    sha256 "PLACEHOLDER"
  end

  resource "libtmux" do
    url "https://files.pythonhosted.org/packages/source/l/libtmux/libtmux-0.37.0.tar.gz"
    sha256 "PLACEHOLDER"
  end

  # Additional transitive dependencies would go here
  # Run `poet -r tmux-ctl` to generate the full resource stanzas

  def install
    virtualenv_install_with_resources
  end

  test do
    # Start server briefly and check it responds
    fork do
      exec bin/"tmux-ctl", "--port", "18765"
    end
    sleep 2
    output = shell_output("curl -s http://127.0.0.1:18765/")
    assert_match "tmux-ctl", output
  end
end
