alias cl='clear'
alias cf='/proj/MIT-DoS/exp/coap-setup/deps/californium'
alias l='-ls -ltrh'

function hg () {
  eval "history | grep $@"
}
export -f hg

function pg () {
  eval "ps aux | grep $@"
}
export -f pg