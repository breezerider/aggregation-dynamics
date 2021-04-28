
import numpy as np
import scipy.optimize

class FitModel:
  
  @staticmethod
  def objective(x, *params):
    return FitModel.function(x, *params) + FitModel.constraints(*params)
  
  @staticmethod
  def function(x, *params):
    raise NotImplementedError('You need to define a function method!')

  @staticmethod
  def constraints(*params):
    raise NotImplementedError('You need to define a constraints method!')

  @staticmethod
  def initialguess():
    raise NotImplementedError('You need to define a initialcond method!')
  

class FitModelExp(FitModel):
  
  @staticmethod
  def objective(params, x, y):
    return np.sum((FitModelExp.error(params, x, y))**2)
  
  @staticmethod
  def error(params, x, y):
    return y - FitModelExp.function(x, params[0])

  @staticmethod
  def function(x, p0):
    return np.exp( - p0 * x )

  @staticmethod
  def jac(x, p0):
    return np.array([ - x * np.exp( - p0 * x ) ]).T

  #@staticmethod
  #def jac(params, x, y):
    ###print(f'params : {params}')
    #return [ np.sum( x * np.exp( - params[0] * x ) * 2.0 * FitModelHyp.error(params, x, y) ) ]

  @staticmethod
  def hess(params, x, y):
    return [
      [ np.sum(x * x * np.exp( - params[0] * x )) ]
    ]

  @staticmethod
  def initialguess():
    return np.array([10] , dtype=float) + np.array([5], dtype=float) * (np.random.rand(1) - 0.5)

  @staticmethod
  def constraints():
    return []
  
  @staticmethod
  def bounds():
    return ([0], [np.inf])
  #scipy.optimize.Bounds([0.0], [np.inf])
  #

class FitModelDblExp(FitModel):

  @staticmethod
  def objective(params, x, y):
    return np.sum((FitModelDblExp.error(params, x, y))**2)
  
  @staticmethod
  def error(params, x, y):
    return y - FitModelDblExp.function(x, params[0], params[1])

  @staticmethod
  def function(x, p0, p1):
    return 0.5 * (np.exp( - p0 * x ) + np.exp( - p1 * x ))

  @staticmethod
  def jac(x, p0, p1):
    return np.array([ 
      - x * np.exp( - p0 * x ),
      - x * np.exp( - p1 * x )
    ]).T

  #@staticmethod
  #def jac(params, x, y):
    ###print(f'params : {params}')
    #return [ 
      #np.sum( x * np.exp( - params[0] * x ) * 2.0 * FitModelHyp.error(params, x, y) ),
      #np.sum( x * np.exp( - params[1] * x ) * 2.0 * FitModelHyp.error(params, x, y) )
      #]

  @staticmethod
  def hess(params, x, y):
    return [
      [ np.sum(x * x * np.exp( - params[0] * x )),
        np.sum(-x * (np.exp( - params[0] * x ) + np.exp( - params[1] * x )) )
      ],
      [ np.sum(-x * (np.exp( - params[0] * x ) + np.exp( - params[1] * x )) ),
        np.sum(x * x * np.exp( - params[1] * x ))
      ]
    ]

  @staticmethod
  def constraints():
    return [scipy.optimize.LinearConstraint([[1, -1]], [0], [np.inf])]
  #[{"type": "ineq", "fun": lambda x: x[1] - x[0]}]
  
  @staticmethod
  def bounds():
    return ([0, 0], [np.inf, np.inf])
  #scipy.optimize.Bounds([0.0, 0.0], [np.inf, np.inf])

  @staticmethod
  def initialguess():
    return np.array([10, 20] , dtype=float) + np.array([5, 10], dtype=float) * (np.random.rand(2) - 0.5)

class FitModelDblExpFix(FitModel):

  @staticmethod
  def objective(params, x, y):
    return np.sum((FitModelDblExpFix.error(params, x, y))**2)
  
  @staticmethod
  def error(params, x, y):
    return y - FitModelDblExpFix.function(x, params[0])

  @staticmethod
  def function(x, p0):
    return 0.5 * (np.exp( - 1.0/0.05 * x ) + np.exp( - p0 * x ))

  @staticmethod
  def jac(x, p0):
    ##print(f'params : {params}')
    return np.array([ - x * np.exp( - p0 * x ) ]).T

  #@staticmethod
  #def jac(params, x, y):
    ###print(f'params : {params}')
    #return [ 
      #np.sum( x * np.exp( - params[0] * x ) * 2.0 * FitModelHyp.error(params, x, y) )
      #]

  @staticmethod
  def hess(params, x, y):
    return [
      [ np.sum(x * x * np.exp( - params[0] * x )),
        np.sum(-x * (np.exp( - params[0] * x ) + np.exp( - params[1] * x )) )
      ],
      [ np.sum(-x * (np.exp( - params[0] * x ) + np.exp( - params[1] * x )) ),
        np.sum(x * x * np.exp( - params[1] * x ))
      ]
    ]

  @staticmethod
  def constraints():
    return []
  #[{"type": "ineq", "fun": lambda x: x[1] - x[0]}]
  
  @staticmethod
  def bounds():
    return ([0], [np.inf])
  #scipy.optimize.Bounds([0.0], [np.inf])

  @staticmethod
  def initialguess():
    return np.array([20] , dtype=float) + np.array([10], dtype=float) * (np.random.rand(1) - 0.5)

class FitModelSclDblExp(FitModel):
  
  @staticmethod
  def objective(params, x, y):
    return np.sum((FitModelSclDblExp.error(params, x, y))**2)
  
  @staticmethod
  def error(params, x, y):
    return y - FitModelSclDblExp.function(x, params[0], params[1], params[2])

  @staticmethod
  def function(x, p0, p1, p2):
    return p0 * np.exp( - p1 * x ) + (1 - p0) * np.exp( - p2 * x )

  @staticmethod
  def jac(x, p0, p1, p2):
    return np.array([ 
      np.exp( - p1 * x ) - np.exp( - p2 * x ),
      - x * p0 * np.exp( - p1 * x ),
      - x * (1.0 - p0) * np.exp( - p2 * x )
    ]).T

  #@staticmethod
  #def jac(params, x, y):
    ##print(f'params : {params}')
    #return [ 
      #np.sum( - 1.0 * (np.exp( - params[1] * x ) - np.exp( - params[2] * x )) * 2.0 * FitModelHyp.error(params, x, y) ),
      #np.sum( x * params[0] * np.exp( - params[1] * x ) * 2.0 * FitModelHyp.error(params, x, y) ),
      #np.sum( x * (1.0 - params[0]) * np.exp( - params[2] * x ) * 2.0 * FitModelHyp.error(params, x, y) )
      #]

  #@staticmethod
  #def hess(params, x, y):
    #return [
      #[ np.sum(x * x * np.exp( - params[0] * x )), np.sum(-x * (np.exp( - params[0] * x ) + np.exp( - params[1] * x )) ],
      #[ np.sum(-x * (np.exp( - params[0] * x ) + np.exp( - params[1] * x )), np.sum(x * x * np.exp( - params[1] * x )) ]
    #]

  @staticmethod
  def constraints():
    return [scipy.optimize.LinearConstraint([[1, -1, 0]], [0], [np.inf])]
  #[{"type": "ineq", "fun": lambda x: x[2] - x[1]}]
  
  @staticmethod
  def bounds():
    return ([0, 0, 0], [1.0, np.inf, np.inf])
  #scipy.optimize.Bounds([0.0, 0.0, 0.0], [1.0, np.inf, np.inf])

  @staticmethod
  def initialguess():
    return np.array([0.5, 10, 20] , dtype=float) + np.array([0.25, 5, 10], dtype=float) * (np.random.rand(3) - 0.5)

class FitModelHyp(FitModel):
  
  @staticmethod
  def objective(params, x, y):
    return np.sum((FitModelHyp.error(params, x, y))**2)
  
  @staticmethod
  def error(params, x, y):
    return y - FitModelHyp.function(x, params[0])

  @staticmethod
  def function(x, p0):
    return np.power( 1.0 + x, - p0 )

  @staticmethod
  def jac(x, p0):
    ##print(f'params : {params}')
    return np.array([  - p0 * np.power( 1.0 + x, - p0 - 1.0 ) ]).T

  #@staticmethod
  #def jac(params, x, y):
    ###print(f'params : {params}')
    #return [ np.sum(p0 * np.power( 1.0 + x, - p0 - 1.0 ) * 2.0 * FitModelHyp.error(params, x, y)) ]

  @staticmethod
  def hess(params, x, y):
    return [
      [ np.sum(x * x * np.exp( - params[0] * x )) ]
    ]

  @staticmethod
  def initialguess():
    return np.array([1] , dtype=float) + np.array([ 0.5 ], dtype=float) * (np.random.rand(1) - 0.5)

  @staticmethod
  def constraints():
    return []
  
  @staticmethod
  def bounds():
    return ([0], [np.inf])
  #scipy.optimize.Bounds([0.0], [np.inf])
  #
Models = {'exp' : FitModelExp, 'dblexp' : FitModelDblExp, 'dblexpfix' : FitModelDblExpFix, 'scldblexp' : FitModelSclDblExp, 'hyp' : FitModelHyp }
ModelNames = {'exp' : 'Exponetial', 'dblexp' : 'Double Exponetial', 'dblexpfix' : 'Double Exponetial (first fixed at 1)', 'scldblexp' : 'Scaled Doube Exponetial', 'hyp' : 'Hyperbola' } 
