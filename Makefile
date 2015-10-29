NAME = influx
REPO_URL = github.com/influxdb/influxdb
VERSION ?= 0.9.5

####################
## GIT PARAMETERS ##
####################

GIT_BRANCH := $(shell sh -c 'git rev-parse --abbrev-ref HEAD')
GIT_LONG_COMMIT := $(shell sh -c 'git rev-parse HEAD')
GIT_SHORT_COMMIT := $(shell sh -c 'git log --pretty=format:"%h" -n 1')

######################
## BUILD PARAMETERS ##
######################

DATE := $(shell sh -c 'date -u +%Y-%m-%dT%H:%M:%S+0000')
CURRENT_DIR := $(shell sh -c 'pwd')
LN_DIR := $(shell sh -c 'dirname $(REPO_URL)')
TARGET_DIR=target
# gox specific os-arch flags, must have gox listed in GO_DEPS
OS_ARCH=linux/386 linux/amd64 darwin/amd64 windows/amd64 linux/arm
LDFLAGS=-X main.version=$(VERSION) -X main.branch=$(GIT_BRANCH) -X main.commit=$(GIT_LONG_COMMIT)

###################
## GO PARAMETERS ##
###################

GO=go
export GOBIN ?= $(GOPATH)/bin
GO_DEPS = github.com/mitchellh/gox \
	  github.com/tcnksm/ghr

build: prepare
	@echo "Builds will be located here: $(CURRENT_DIR)$(TARGET_DIR)/"
	$(GO) build -o $(TARGET_DIR)/$(NAME) -ldflags="$(LDFLAGS)" ./cmd/$(NAME)/main.go
	$(GO) build -o $(TARGET_DIR)/$(NAME)d -ldflags="$(LDFLAGS)" ./cmd/$(NAME)d/main.go
	$(GO) build -o $(TARGET_DIR)/$(NAME)_stress -ldflags="$(LDFLAGS)" ./cmd/$(NAME)_stress/$(NAME)_stress.go
	$(GO) build -o $(TARGET_DIR)/$(NAME)_inspect -ldflags="$(LDFLAGS)" ./cmd/$(NAME)_inspect/*.go

dist: prepare
ifeq ($(NIGHTLY), true)
	rm -rf $(TARGET_DIR)
	mkdir $(TARGET_DIR)
	gox -ldflags="$(LDFLAGS)" \
		-osarch="$(OS_ARCH)" \
		-output "$(TARGET_DIR)/{{.OS}}_{{.Arch}}/{{.Dir}}_$(VERSION)_nightly_$(GIT_SHORT_COMMIT)_{{.OS}}_{{.Arch}}" \
		./cmd/$(NAME) \
		./cmd/$(NAME)d \
		./cmd/$(NAME)_inspect \
		./cmd/$(NAME)_stress
else
		rm -rf $(TARGET_DIR)
		mkdir $(TARGET_DIR)
		gox -ldflags="$(LDFLAGS)" \
			-osarch="$(OS_ARCH)" \
			-output "$(TARGET_DIR)/{{.OS}}_{{.Arch}}/{{.Dir}}_$(VERSION)_{{.OS}}_{{.Arch}}" \
			./cmd/$(NAME) \
			./cmd/$(NAME)d \
			./cmd/$(NAME)_inspect \
			./cmd/$(NAME)_stress
endif

release: target
	ghr -u influxdb -r $(NAME) $(GIT_SHORT_VERSION) $(TARGET_DIR)/

update:
	$(GO) get -u -t ./...

prepare:
	$(GO) get -t ./...
	@for dep in $(GO_DEPS); do \
		echo "Retrieving Go dependency:" $$dep; \
		$(GO) get $$dep; \
	done

test: prepare
	$(GO) tool vet --composites=false ./
	$(GO) test ./...

test-short: prepare
	$(GO) test -short ./...

.PHONY: test
