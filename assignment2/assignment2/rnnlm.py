from numpy import *
import numpy as np
import itertools
import time
import sys
import cPickle as pickle

# Import NN utils
from nn.base import NNBase
from nn.math import softmax, sigmoid, sigmoidGrad,make_onehot
from nn.math import MultinomialSampler, multinomial_sample
from misc import random_weight_matrix


class RNNLM(NNBase):
    """
    Implements an RNN language model of the form:
    h(t) = sigmoid(H * h(t-1) + L[x(t)])                    #  h(t) = sigmoid(H*h(t-1) + W*L[x(t)])
    y(t) = softmax(U * h(t))
    where y(t) predicts the next word in the sequence

    U = |V| * dim(h) as output vectors                      #  lreg 
    L = |V| * dim(h) as input vectors

    You should initialize each U[i,j] and L[i,j]
    as Gaussian noise with mean 0 and variance 0.1
    For random samples from N(mu, sigma^2), use:
    sigma * np.random.randn(...) + mu

    Arguments:
        L0 : initial input word vectors
        U0 : initial output word vectors
        alpha : default learning rate
        bptt : number of backprop timesteps
    """

    def __init__(self, L0, U0=None,
                 alpha=0.005, lreg = 0.00001, rseed=10, bptt=1,loadData=False):
        
        self.hdim = L0.shape[1] # word vector dimensions
        self.vdim = L0.shape[0] # vocab size
        param_dims = dict(H = (self.hdim, self.hdim), W = (self.hdim,self.hdim),
                          U = L0.shape)
        # note that only L gets sparse updates
        param_dims_sparse = dict(L = L0.shape)
        NNBase.__init__(self, param_dims, param_dims_sparse)

        self.alpha = alpha
        self.lreg = lreg
        #### YOUR CODE HERE ####
        
        # Initialize word vectors
        # either copy the passed L0 and U0 (and initialize in your notebook)
        # or initialize with gaussian noise here

        # Initialize H matrix, as with W and U in part 1
        self.bptt = bptt
        if loadData == True:
            with open("rnnlmWithW_hdim_150_bptt_4.H.npy") as fid:
                H = pickle.load(fid)
                self.params.H = H
            with open("rnnlmWithW_hdim_150_bptt_4.W.npy") as fid:
                W = pickle.load(fid)
                self.params.W = W
            with open("rnnlmWithW_hdim_150_bptt_4.U.npy") as fid:
                U = pickle.load(fid)
                self.params.U = U
            with open("rnnlmWithW_hdim_150_bptt_4.L.npy") as fid:
                L = pickle.load(fid)
                self.sparams.L = L
            return

        random.seed(rseed)
        self.params.H = random_weight_matrix(*self.params.H.shape)
        self.params.W = random_weight_matrix(*self.params.W.shape)
        self.params.U = 0.1*np.random.randn(*L0.shape)
        self.sparams.L = L0.copy()
        #### END YOUR CODE ####


    def _acc_grads(self, xs, ys):
        """
        Accumulate gradients, given a pair of training sequences:
        xs = [<indices>] # input words
        ys = [<indices>] # output words (to predict)

        Your code should update self.grads and self.sgrads,
        in order for gradient_check and training to work.

        So, for example:
        self.grads.H += (your gradient dJ/dH)
        self.sgrads.L[i] = (gradient dJ/dL[i]) # update row

        Per the handout, you should:
            - make predictions by running forward in time
                through the entire input sequence
            - for *each* output word in ys, compute the
                gradients with respect to the cross-entropy
                loss for that output word
            - run backpropagation-through-time for self.bptt
                timesteps, storing grads in self.grads (for H, U)
                and self.sgrads (for L)

        You'll want to store your predictions \hat{y}(t)
        and the hidden layer values h(t) as you run forward,
        so that you can access them during backpropagation.
        
        At time 0, you should initialize the hidden layer to
        be a vector of zeros.
        """

        # Expect xs as list of indices
        ns = len(xs)

        # make matrix here of corresponding h(t)
        # hs[-1] = initial hidden state (zeros)
        hs = np.zeros((ns+1, self.hdim))
        # predicted probas
        ps = np.zeros((ns+1, self.vdim))

        #### YOUR CODE HERE ####
        ##
        # Forward propagation

        zs = np.zeros((ns+1,self.hdim))
        for i in range(ns):
            zs[i+1] = self.params.H.dot(hs[i]) + self.params.W.dot(self.sparams.L[xs[i]])
            hs[i+1] = sigmoid(zs[i+1])
            ps[i+1] = softmax(self.params.U.dot(hs[i+1]))
        ##
        # Backward propagation through time
        sgradsTmp = np.zeros((self.vdim,self.hdim)) 
        grad0 = np.zeros((ns+1,self.hdim)) # (y-t)*U 
        for i in range(ns):
            grad0[i+1] = (ps[i+1]-make_onehot(ys[i],self.vdim)).dot(self.params.U)
            self.grads.U += np.outer((ps[i+1]-make_onehot(ys[i],self.vdim)),hs[i+1])
            vectorCurrent = grad0[i+1]*sigmoidGrad(zs[i+1])
            for j in range(min(i+1,self.bptt+1)):
                xh1 = np.ones((self.hdim, self.hdim)).dot(np.diag(hs[i-j]))
                self.grads.H += np.diag(vectorCurrent).dot(xh1)
                x1 = np.ones((self.hdim, self.hdim)).dot(np.diag(self.sparams.L[xs[i-j]]))
                self.grads.W += np.diag(vectorCurrent).dot(x1)
                sgradsTmp[xs[i-j]] += vectorCurrent.dot(self.params.W)
                
                vectorCurrent = vectorCurrent.dot(self.params.H)
                vectorCurrent = vectorCurrent*sigmoidGrad(zs[i-j])

        self.grads.U += self.lreg*self.params.U
        self.grads.H += self.lreg*self.params.H
        self.grads.W += self.lreg*self.params.W
        
        for i in range(len(sgradsTmp)):
            self.sgrads.L[i] = sgradsTmp[i,:]
        #### END YOUR CODE ####


    def grad_check(self, x, y, outfd=sys.stderr, **kwargs):
        """
        Wrapper for gradient check on RNNs;
        ensures that backprop-through-time is run to completion,
        computing the full gradient for the loss as summed over
        the input sequence and predictions.

        Do not modify this function!
        """
        bptt_old = self.bptt
        self.bptt = len(y)
        print >> outfd, "NOTE: temporarily setting self.bptt = len(y) = %d to compute true gradient." % self.bptt
        NNBase.grad_check(self, x, y, outfd=outfd, **kwargs)
        self.bptt = bptt_old
        print >> outfd, "Reset self.bptt = %d" % self.bptt


    def compute_seq_loss(self, xs, ys):
        """
        Compute the total cross-entropy loss
        for an input sequence xs and output
        sequence (labels) ys.

        You should run the RNN forward,
        compute cross-entropy loss at each timestep,
        and return the sum of the point losses.
        """

        J = 0
        #### YOUR CODE HERE ####
        ns = len(xs)
        hs = np.zeros((ns+1,self.hdim))
        for i in range(ns):
            hs[i+1] = sigmoid(self.params.H.dot(hs[i])+self.params.W.dot(self.sparams.L[xs[i]]))
            p = softmax(self.params.U.dot(hs[i+1]))
            p = p*make_onehot(ys[i],self.vdim)
            J += -np.log(np.sum(p))
        #### END YOUR CODE ####

        Jreg = 0.5*self.lreg*(np.sum(self.params.H**2)+np.sum(self.params.W**2)+np.sum(self.params.U**2))
        return J + Jreg


    def compute_loss(self, X, Y):
        """
        Compute total loss over a dataset.
        (wrapper for compute_seq_loss)

        Do not modify this function!
        """
        if not isinstance(X[0], ndarray): # single example
            return self.compute_seq_loss(X, Y)
        else: # multiple examples
            return sum([self.compute_seq_loss(xs,ys)
                       for xs,ys in itertools.izip(X, Y)])

    def compute_mean_loss(self, X, Y):
        """
        Normalize loss by total number of points.

        Do not modify this function!
        """
        J = self.compute_loss(X, Y)
        ntot = sum(map(len,Y))
        return J / float(ntot)


    def generate_sequence(self, init, end, maxlen=100):
        """
        Generate a sequence from the language model,
        by running the RNN forward and selecting,
        at each timestep, a random word from the
        a word from the emitted probability distribution.

        The MultinomialSampler class (in nn.math) may be helpful
        here for sampling a word. Use as:

            y = multinomial_sample(p)

        to sample an index y from the vector of probabilities p.


        Arguments:
            init = index of start word (word_to_num['<s>'])
            end = index of end word (word_to_num['</s>'])
            maxlen = maximum length to generate

        Returns:
            ys = sequence of indices
            J = total cross-entropy loss of generated sequence
        """
        J = 0 # total loss
        ys = [init] # emitted sequence

        ns = maxlen
        hs = np.zeros((ns+1,self.hdim))
        #### YOUR CODE HERE ####
        for i in range(ns):
            hs[i+1] = sigmoid(self.params.H.dot(hs[i])+self.params.W.dot(self.sparams.L[ys[i]]))
            p = softmax(self.params.U.dot(hs[i+1]))
            y = multinomial_sample(p)
            ys.append(y)
            if y == end:
                break
            p = p*make_onehot(y,self.vdim)
            J += -np.log(np.sum(p))
            
        Jreg = 0.5*self.lreg*(np.sum(self.params.H**2)+np.sum(self.params.W**2)+np.sum(self.params.U**2))
        #### YOUR CODE HERE ####
        return ys, J+Jreg



class ExtraCreditRNNLM(RNNLM):
    """
    Implements an improved RNN language model,
    for better speed and/or performance.

    We're not going to place any constraints on you
    for this part, but we do recommend that you still
    use the starter code (NNBase) framework that
    you've been using for the NER and RNNLM models.
    """

    def __init__(self, *args, **kwargs):
        #### YOUR CODE HERE ####
        raise NotImplementedError("__init__() not yet implemented.")
        #### END YOUR CODE ####

    def _acc_grads(self, xs, ys):
        #### YOUR CODE HERE ####
        raise NotImplementedError("_acc_grads() not yet implemented.")
        #### END YOUR CODE ####

    def compute_seq_loss(self, xs, ys):
        #### YOUR CODE HERE ####
        raise NotImplementedError("compute_seq_loss() not yet implemented.")
        #### END YOUR CODE ####

    def generate_sequence(self, init, end, maxlen=100):
        #### YOUR CODE HERE ####
        raise NotImplementedError("generate_sequence() not yet implemented.")
        #### END YOUR CODE ####


def save_params(filename,params):
    with open(filename,"w") as f:
        pickle.dump(params,f)


def seq_to_words(seq):
    return [num_to_word[s] for s in seq]

def adjust_loss(loss, funk, q, mode='basic'):
    if mode == 'basic':
        return (loss + funk*log(funk))/(1-funk)
    else:
        return loss + funk*log(funk)-funk*log(q)

def fill_unknowns(words,vocab):
    ret = words
    p = np.array([freq for word, freq in dict(vocab["freq"]).items()])
    #print "summize all probability -> ",np.sum(p)
    for i in range(len(words)):
        if words[i] == "UUUNKKK":
            ret[i] = vocab.index[multinomial_sample(p)]
        else:
            ret[i] = words[i]
    return ret

if __name__ == "__main__":
    random.seed(10)
    wv_dummy = random.randn(10,50)
    model = RNNLM(L0 = wv_dummy, U0=wv_dummy,alpha=0.005,lreg=0.000001,rseed=10,bptt=4)
    model.grad_check(np.array([0,1,2,3]),np.array([1,2,3,4]))
    #model.grad_check(x=[1,2,3],y=[2,3,4])
    
    from data_utils import utils as du
    import pandas as pd

    vocab = pd.read_table("data/lm/vocab.ptb.txt",header=None, sep="\s+", index_col=0, names=['count','freq'])
    vocabsize = 6000
    num_to_word = dict(enumerate(vocab.index[:vocabsize]))
    word_to_num = du.invert_dict(num_to_word)

    fraction_lost = float(sum([vocab['count'][word] for word in vocab.index
                               if (not word in word_to_num) and
                               (not word == "UUUNKKK")]))
    fraction_lost /= sum([vocab['count'][word] for word in vocab.index
                          if (not word == "UUUNKKK")])
    print "Retained %d words from %d (%.02f%% of all tokens)" %(vocabsize,len(vocab),100*(1-fraction_lost))

    docs = du.load_dataset('data/lm/ptb-train.txt')
    S_train = du.docs_to_indices(docs, word_to_num)
    X_train, Y_train = du.seqs_to_lmXY(S_train)
    
    docs = du.load_dataset('data/lm/ptb-dev.txt')
    S_dev = du.docs_to_indices(docs, word_to_num)
    X_dev, Y_dev = du.seqs_to_lmXY(S_dev)
    
    docs = du.load_dataset('data/lm/ptb-test.txt')
    S_test = du.docs_to_indices(docs,word_to_num)
    X_test, Y_test = du.seqs_to_lmXY(S_test)

    #print " ".join(d[0] for d in docs[7])
    #print " ".join(num_to_word[i] for i in S_test[7])

    #For random samples from N(mu, sigma^2), use:
    #    sigma * np.random.randn(...) + mu

    
    hdim = 150
    bptt = 4
    random.seed(10)
    L0 = 0.1*np.random.randn(vocabsize,hdim)
    model = None
    loadData = True
    #model.grad_check(np.array([1,2,3]),np.array([2,3,4]))

    if loadData == True:
        model = RNNLM(L0, U0=L0, alpha=0.1, rseed=10, bptt=bptt,loadData=True)
    else:
        model = RNNLM(L0, U0=L0, alpha=0.1, rseed=10, bptt=bptt)
        trainCost = model.train_sgd(X_train, Y_train)
        save_params("rnnlmWithW_hdim_%d_bptt_%d.L.npy"%(hdim,bptt), model.sparams.L)
        save_params("rnnlmWithW_hdim_%d_bptt_%d.U.npy"%(hdim,bptt), model.params.U)
        save_params("rnnlmWithW_hdim_%d_bptt_%d.W.npy"%(hdim,bptt), model.params.W)
        save_params("rnnlmWithW_hdim_%d_bptt_%d.H.npy"%(hdim,bptt), model.params.H)


    for i in range(10):
        seq, J = model.generate_sequence(word_to_num["<s>"],word_to_num["</s>"],maxlen=100)
        print J
        #print " ".join(seq_to_words(seq))
        print " ".join(fill_unknowns(seq_to_words(seq),vocab))
    
    #dev_loss = model.compute_mean_loss(X_dev, Y_dev)
    #q = vocab.freq[vocabsize]/np.sum(vocab.freq[vocabsize:])
    #print "Unadjusted: %.03f" % np.exp(dev_loss)
    #print "Adjusted for missing vocab: %.03f" % np.exp(adjust_loss(dev_loss,fraction_lost,q))

    
    
    
